package backend

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// serviceTokenHeader is the shared-secret header expected by the backend
// (src/auth/api.py).
const serviceTokenHeader = "X-Service-Token" //nolint:gosec // header name, not a secret

// defaultHTTPTimeout bounds every backend call so a stalled data plane cannot
// pin a tool call open forever.
const defaultHTTPTimeout = 15 * time.Second

// maxResponseBytes caps how much of a backend response body is buffered.
const maxResponseBytes = 8 << 20 // 8 MiB

// ValidateBaseURL rejects values that parse but cannot address an HTTP origin
// (for example "not-a-url" or "ftp://host"), so a misconfigured environment
// fails at startup instead of on the first backend call.
func ValidateBaseURL(raw string) error {
	trimmed := strings.TrimRight(strings.TrimSpace(raw), "/")
	if trimmed == "" {
		return errors.New("backend base URL is required")
	}
	parsed, err := url.Parse(trimmed)
	if err != nil {
		return fmt.Errorf("backend base URL is not a valid URL: %w", err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return errors.New("backend base URL must use http or https")
	}
	if parsed.Host == "" {
		return errors.New("backend base URL must include a host")
	}
	return nil
}

// Options configures a Transport.
type Options struct {
	BaseURL        string
	MaxConcurrency int
	RequestTimeout time.Duration
}

// Transport executes outbound HTTP calls to the backend data plane.
type Transport struct {
	baseURL        *url.URL
	httpClient     *http.Client
	maxConcurrency int
	sem            chan struct{}
	requestTimeout time.Duration
}

// NewTransport validates opts and builds a Transport. opts.BaseURL must be
// an absolute http(s) origin. opts.MaxConcurrency caps concurrent outbound
// requests and must be > 0.
func NewTransport(opts Options) (*Transport, error) {
	if opts.MaxConcurrency <= 0 {
		return nil, errors.New("max concurrency must be greater than 0")
	}

	if err := ValidateBaseURL(opts.BaseURL); err != nil {
		return nil, err
	}

	trimmed := strings.TrimRight(strings.TrimSpace(opts.BaseURL), "/")
	parsed, _ := url.Parse(trimmed)

	timeout := opts.RequestTimeout
	if timeout <= 0 {
		timeout = defaultHTTPTimeout
	}

	return &Transport{
		baseURL:        parsed,
		httpClient:     &http.Client{Timeout: timeout},
		maxConcurrency: opts.MaxConcurrency,
		sem:            make(chan struct{}, opts.MaxConcurrency),
		requestTimeout: timeout,
	}, nil
}

// RouteGroup isolates path prefix and authentication token for a data domain
// on top of a shared Transport.
type RouteGroup struct {
	transport *Transport
	prefix    string
	token     string
}

// NewRouteGroup creates a new RouteGroup with the given path prefix and token.
func (t *Transport) NewRouteGroup(prefix, token string) *RouteGroup {
	p := strings.TrimRight(strings.TrimSpace(prefix), "/")
	if p != "" && !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	return &RouteGroup{
		transport: t,
		prefix:    p,
		token:     token,
	}
}

// Do performs an HTTP request against the route group, enforcing concurrency limits,
// serializing body (if non-nil) to JSON, and decoding a 2xx JSON body into out (if non-nil).
// Every failure is normalized to one of the ErrNoData / ErrValidation / ErrConfiguration /
// ErrProvider classes.
func (g *RouteGroup) Do(ctx context.Context, method, path string, query url.Values, body any, out any) error {
	start := time.Now()
	if g.transport.requestTimeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, g.transport.requestTimeout)
		defer cancel()
	}
	p := path
	if p != "" && !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	rawURL := g.transport.baseURL.String() + g.prefix + p
	endpoint, err := url.Parse(rawURL)
	if err != nil {
		bErr := &Error{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", rawURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	if query != nil {
		endpoint.RawQuery = query.Encode()
	}
	reqURL := endpoint.String()

	select {
	case g.transport.sem <- struct{}{}:
	case <-ctx.Done():
		bErr := &Error{class: ErrProvider, detail: ctx.Err().Error()}
		slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
		return bErr
	default:
		slog.WarnContext(ctx, "backend concurrency limit reached, queuing call", slog.Int("max_concurrency", g.transport.maxConcurrency), slog.String("url", reqURL))
		select {
		case g.transport.sem <- struct{}{}:
		case <-ctx.Done():
			bErr := &Error{class: ErrProvider, detail: ctx.Err().Error()}
			slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
			return bErr
		}
	}
	defer func() { <-g.transport.sem }()

	var reqBody io.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			bErr := &Error{class: ErrProvider, detail: err.Error()}
			slog.ErrorContext(ctx, "backend request failed",
				slog.String("url", reqURL),
				slog.Int("status", 0),
				slog.String("detail", bErr.Detail()),
			)
			return bErr
		}
		reqBody = bytes.NewReader(payload)
	}

	req, err := http.NewRequestWithContext(ctx, method, reqURL, reqBody)
	if err != nil {
		bErr := &Error{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if g.token != "" {
		req.Header.Set(serviceTokenHeader, g.token)
	}
	req.Header.Set("Accept", "application/json")

	slog.DebugContext(ctx, "backend request",
		slog.String("method", method),
		slog.String("url", reqURL),
		slog.String("query", query.Encode()),
	)

	resp, err := g.transport.httpClient.Do(req)
	duration := time.Since(start)
	if err != nil {
		bErr := &Error{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	defer resp.Body.Close()

	slog.DebugContext(ctx, "backend response",
		slog.String("method", method),
		slog.String("url", reqURL),
		slog.Int("status", resp.StatusCode),
		slog.Duration("duration", duration),
	)

	bodyBytes, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		bErr := &Error{class: ErrProvider, status: resp.StatusCode, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bErr := classifyBackendError(resp.StatusCode, bodyBytes)
		var detail string
		if be, ok := bErr.(*Error); ok {
			detail = be.Detail()
		}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.String("detail", detail),
		)
		return bErr
	}

	if out != nil {
		if err := json.Unmarshal(bodyBytes, out); err != nil {
			bErr := &Error{
				class:  ErrProvider,
				status: resp.StatusCode,
				detail: "malformed response from the market data service",
			}
			slog.ErrorContext(ctx, "backend request failed",
				slog.String("url", reqURL),
				slog.Int("status", resp.StatusCode),
				slog.String("detail", bErr.Detail()),
			)
			return bErr
		}
	}
	return nil
}

// Get performs a GET request against the route group and decodes a 2xx JSON body into out.
func (g *RouteGroup) Get(ctx context.Context, path string, query url.Values, out any) error {
	return g.Do(ctx, http.MethodGet, path, query, nil, out)
}

// Post performs a POST request with a JSON body against the route group and decodes a 2xx JSON body into out.
func (g *RouteGroup) Post(ctx context.Context, path string, query url.Values, body any, out any) error {
	return g.Do(ctx, http.MethodPost, path, query, body, out)
}
