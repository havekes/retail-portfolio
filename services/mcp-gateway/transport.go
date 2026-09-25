package main

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
	"strconv"
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

// errorDetailLimit caps the diagnostic detail retained on a backendError.
const errorDetailLimit = 512

// Error taxonomy for backend failures. These sentinels are the contract T11's
// tools map onto MCP results:
//
//   - ErrNoData: the backend has no data for the request right now. This is a
//     normal outcome (404 may be a cached empty result within the TTL) and must
//     never be presented as "invalid symbol".
//   - ErrValidation: the request's parameters failed backend validation (422).
//     Unlike ErrNoData, retrying with corrected parameters is the right
//     response, so the parsed validation message is forwarded to the agent.
//   - ErrConfiguration: the service token was rejected. This is an operator
//     problem, not a user one.
//   - ErrProvider: the market data provider is unreachable or misbehaving.
//
// The sentinel messages are deliberately generic: they contain neither the
// service token nor any provider name, so they are safe to surface to an agent.
var (
	ErrNoData        = errors.New("no market data found")
	ErrValidation    = errors.New("market data request was invalid")
	ErrConfiguration = errors.New("market data authentication failed — check service token configuration")
	ErrProvider      = errors.New("market data is temporarily unavailable")
)

// backendError classifies a backend failure while keeping Error() generic.
//
// The underlying detail (status code and a truncated response body) is retained
// for Go-side diagnostics only; it is intentionally excluded from Error() so a
// tool handler that forwards err.Error() cannot leak internals to an agent.
//
// validation carries the agent-safe message parsed from a 422 body, if any. Only
// ErrValidation populates it.
type backendError struct {
	class      error
	status     int
	detail     string
	validation string
}

func (e *backendError) Error() string { return e.class.Error() }

// Unwrap exposes the sentinel so errors.Is(err, ErrNoData) &c. keep working.
func (e *backendError) Unwrap() error { return e.class }

// Status returns the HTTP status that produced the error, or 0 for transport
// and decoding failures.
func (e *backendError) Status() int { return e.status }

// Detail returns the Go-side diagnostic detail. It must not be forwarded to
// agent-facing output.
func (e *backendError) Detail() string { return e.detail }

// ValidationMessage returns the agent-safe message parsed from a 422 body, or
// "" when the error is not a validation failure or the body was unparsable. It
// contains only the backend's validation text — never a status, token or
// provider name — so it is safe to forward to an agent.
func (e *backendError) ValidationMessage() string { return e.validation }

// classifyBackendError maps a non-2xx backend response onto the error taxonomy.
//
// 404 means "no data for this request"; 422 means the request's parameters
// failed backend validation; 401/403 mean the service token was rejected; every
// other status (including 5xx and unexpected 4xx) is treated as a provider-side
// failure so callers always get one of four classes.
func classifyBackendError(status int, body []byte) error {
	detail := truncateDetail(string(body))
	switch status {
	case http.StatusNotFound:
		return &backendError{class: ErrNoData, status: status, detail: detail}
	case http.StatusUnprocessableEntity:
		return &backendError{
			class:      ErrValidation,
			status:     status,
			detail:     detail,
			validation: validationMessage(body),
		}
	case http.StatusUnauthorized, http.StatusForbidden:
		return &backendError{class: ErrConfiguration, status: status, detail: detail}
	default:
		return &backendError{class: ErrProvider, status: status, detail: detail}
	}
}

// validationLocationKinds are FastAPI's request-location prefixes in a pydantic
// validation error's loc path (e.g. ["query", "expiry"]). They name where the
// invalid parameter lives, not the parameter itself, so they are dropped from
// the rendered path.
var validationLocationKinds = map[string]bool{
	"body": true, "query": true, "path": true, "header": true, "cookie": true,
}

// validationMessage extracts an agent-safe message from a FastAPI 422 body.
//
// FastAPI reports request validation failures as {"detail": ...} where detail is
// either a string or an array of {loc, msg, type} objects. Only the message text
// is echoed — never the raw body, status, or any other backend internal — so the
// result is safe to forward to an agent. Any shape that cannot be parsed falls
// back to the generic ErrValidation text.
func validationMessage(body []byte) string {
	var envelope struct {
		Detail json.RawMessage `json:"detail"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil || len(envelope.Detail) == 0 {
		return ErrValidation.Error()
	}

	var detail string
	if err := json.Unmarshal(envelope.Detail, &detail); err == nil {
		if detail = strings.TrimSpace(detail); detail != "" {
			return truncateDetail(detail)
		}
		return ErrValidation.Error()
	}

	var items []struct {
		Loc []any  `json:"loc"`
		Msg string `json:"msg"`
	}
	if err := json.Unmarshal(envelope.Detail, &items); err == nil {
		messages := make([]string, 0, len(items))
		for _, item := range items {
			msg := strings.TrimSpace(item.Msg)
			if msg == "" {
				continue
			}
			if loc := renderValidationLoc(item.Loc); loc != "" {
				messages = append(messages, loc+" "+msg)
			} else {
				messages = append(messages, msg)
			}
		}
		if len(messages) > 0 {
			return truncateDetail(strings.Join(messages, "; "))
		}
	}

	return ErrValidation.Error()
}

// renderValidationLoc renders a pydantic loc path compactly, dropping any leading
// request-location kind (e.g. ["query", "expiry"] → "expiry"). Numbers (array
// indexes) are preserved. Unsupported element types are skipped defensively.
func renderValidationLoc(loc []any) string {
	parts := make([]string, 0, len(loc))
	for i, element := range loc {
		switch value := element.(type) {
		case string:
			if i == 0 && validationLocationKinds[value] {
				continue
			}
			if value != "" {
				parts = append(parts, value)
			}
		case float64:
			parts = append(parts, strconv.FormatFloat(value, 'f', -1, 64))
		}
	}
	return strings.Join(parts, ".")
}

func truncateDetail(s string) string {
	if len(s) > errorDetailLimit {
		return s[:errorDetailLimit]
	}
	return s
}

// Transport provides the generalized HTTP transport core for talking to
// backend services. Outbound requests are concurrency-capped across all route
// groups sharing the transport.
type Transport struct {
	baseURL        *url.URL
	httpClient     *http.Client
	cfg            Config
	maxConcurrency int
	sem            chan struct{}
}

// NewTransport validates cfg and builds a Transport. cfg.BackendBaseURL must be
// an absolute http(s) origin. cfg.MaxConcurrency caps concurrent outbound
// requests and must be > 0.
func NewTransport(cfg Config) (*Transport, error) {
	if cfg.MaxConcurrency <= 0 {
		return nil, errors.New("max concurrency must be greater than 0")
	}

	trimmed := strings.TrimRight(strings.TrimSpace(cfg.BackendBaseURL), "/")
	if trimmed == "" {
		return nil, errors.New("backend base URL is required")
	}
	parsed, err := url.Parse(trimmed)
	if err != nil {
		return nil, fmt.Errorf("backend base URL is not a valid URL: %w", err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, errors.New("backend base URL must use http or https")
	}
	if parsed.Host == "" {
		return nil, errors.New("backend base URL must include a host")
	}

	return &Transport{
		baseURL:        parsed,
		httpClient:     &http.Client{Timeout: defaultHTTPTimeout},
		cfg:            cfg,
		maxConcurrency: cfg.MaxConcurrency,
		sem:            make(chan struct{}, cfg.MaxConcurrency),
	}, nil
}

// MaxConcurrency returns the maximum number of concurrent outbound requests allowed.
func (t *Transport) MaxConcurrency() int {
	return t.maxConcurrency
}

// BaseURL returns the parsed base URL of the transport.
func (t *Transport) BaseURL() *url.URL {
	return t.baseURL
}

// Config returns the configuration used by this transport.
func (t *Transport) Config() Config {
	return t.cfg
}

// isDev reports whether this transport is running in a development environment.
func (t *Transport) isDev() bool {
	return isDev(t.cfg.Environment)
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

// Prefix returns the route group's path prefix.
func (g *RouteGroup) Prefix() string {
	return g.prefix
}

// Token returns the route group's authentication token.
func (g *RouteGroup) Token() string {
	return g.token
}

// Transport returns the underlying Transport.
func (g *RouteGroup) Transport() *Transport {
	return g.transport
}

// Do performs an HTTP request against the route group, enforcing concurrency limits,
// serializing body (if non-nil) to JSON, and decoding a 2xx JSON body into out (if non-nil).
// Every failure is normalized to one of the ErrNoData / ErrValidation / ErrConfiguration /
// ErrProvider classes.
func (g *RouteGroup) Do(ctx context.Context, method, path string, query url.Values, body any, out any) error {
	start := time.Now()
	p := path
	if p != "" && !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	rawURL := g.transport.baseURL.String() + g.prefix + p
	endpoint, err := url.Parse(rawURL)
	if err != nil {
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
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
		bErr := &backendError{class: ErrProvider, detail: ctx.Err().Error()}
		slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
		return bErr
	default:
		slog.WarnContext(ctx, "backend concurrency limit reached, queuing call", slog.Int("max_concurrency", g.transport.maxConcurrency), slog.String("url", reqURL))
		select {
		case g.transport.sem <- struct{}{}:
		case <-ctx.Done():
			bErr := &backendError{class: ErrProvider, detail: ctx.Err().Error()}
			slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
			return bErr
		}
	}
	defer func() { <-g.transport.sem }()

	var reqBody io.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			bErr := &backendError{class: ErrProvider, detail: err.Error()}
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
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
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

	if g.transport.isDev() {
		slog.DebugContext(ctx, "backend request",
			slog.String("method", method),
			slog.String("url", reqURL),
			slog.String("query", query.Encode()),
		)
	}

	resp, err := g.transport.httpClient.Do(req)
	duration := time.Since(start)
	if err != nil {
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	defer resp.Body.Close()

	if g.transport.isDev() {
		slog.DebugContext(ctx, "backend response",
			slog.String("method", method),
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.Duration("duration", duration),
		)
	}

	bodyBytes, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		bErr := &backendError{class: ErrProvider, status: resp.StatusCode, detail: err.Error()}
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
		if be, ok := bErr.(*backendError); ok {
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
			bErr := &backendError{
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
