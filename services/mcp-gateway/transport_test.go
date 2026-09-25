package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestTransport_NewTransport(t *testing.T) {
	t.Run("valid configuration", func(t *testing.T) {
		cfg := Config{
			BackendBaseURL: "http://backend:8000",
			ServiceToken:   "valid-token",
			MaxConcurrency: 5,
			Environment:    "dev",
		}
		tr, err := NewTransport(cfg)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if tr.MaxConcurrency() != 5 {
			t.Errorf("MaxConcurrency() = %d, want 5", tr.MaxConcurrency())
		}
		if tr.BaseURL().String() != "http://backend:8000" {
			t.Errorf("BaseURL() = %s, want http://backend:8000", tr.BaseURL().String())
		}
		if !tr.isDev() {
			t.Errorf("expected isDev to be true for environment 'dev'")
		}
	})

	t.Run("rejects non-positive max concurrency", func(t *testing.T) {
		for _, val := range []int{0, -1, -10} {
			cfg := Config{
				BackendBaseURL: "http://backend:8000",
				MaxConcurrency: val,
			}
			if _, err := NewTransport(cfg); err == nil {
				t.Errorf("NewTransport with MaxConcurrency=%d expected error, got nil", val)
			}
		}
	})

	t.Run("rejects bad base URLs", func(t *testing.T) {
		for _, raw := range []string{"", "   ", "not-a-url", "ftp://backend:8000", "http://"} {
			cfg := Config{
				BackendBaseURL: raw,
				MaxConcurrency: 10,
			}
			if _, err := NewTransport(cfg); err == nil {
				t.Errorf("NewTransport(%q) expected error, got nil", raw)
			}
		}
	})
}

func TestTransport_GetAndPost(t *testing.T) {
	type requestRecord struct {
		method  string
		path    string
		query   url.Values
		headers http.Header
		body    []byte
	}

	var rec requestRecord
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rec.method = r.Method
		rec.path = r.URL.Path
		rec.query = r.URL.Query()
		rec.headers = r.Header.Clone()
		rec.body, _ = io.ReadAll(r.Body)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"status":"success","received":true}`)
	}))
	defer srv.Close()

	cfg := Config{
		BackendBaseURL: srv.URL,
		ServiceToken:   "secret-token-123",
		MaxConcurrency: 5,
		Environment:    "dev",
	}
	tr, err := NewTransport(cfg)
	if err != nil {
		t.Fatalf("NewTransport: %v", err)
	}

	group := tr.NewRouteGroup("/api/v1/test", "group-token-abc")

	t.Run("GET operation with query parameters", func(t *testing.T) {
		query := url.Values{}
		query.Set("foo", "bar")
		query.Set("limit", "10")

		var out struct {
			Status   string `json:"status"`
			Received bool   `json:"received"`
		}

		err := group.Get(context.Background(), "/items", query, &out)
		if err != nil {
			t.Fatalf("Get failed: %v", err)
		}

		if rec.method != http.MethodGet {
			t.Errorf("method = %s, want GET", rec.method)
		}
		if rec.path != "/api/v1/test/items" {
			t.Errorf("path = %s, want /api/v1/test/items", rec.path)
		}
		if rec.query.Get("foo") != "bar" || rec.query.Get("limit") != "10" {
			t.Errorf("unexpected query: %v", rec.query)
		}
		if rec.headers.Get("X-Service-Token") != "group-token-abc" {
			t.Errorf("X-Service-Token = %q, want group-token-abc", rec.headers.Get("X-Service-Token"))
		}
		if rec.headers.Get("Accept") != "application/json" {
			t.Errorf("Accept = %q, want application/json", rec.headers.Get("Accept"))
		}
		if !out.Received || out.Status != "success" {
			t.Errorf("unexpected output decoded: %+v", out)
		}
	})

	t.Run("POST operation with JSON request body", func(t *testing.T) {
		query := url.Values{}
		query.Set("dry_run", "true")

		reqPayload := map[string]any{
			"name":  "test-item",
			"count": 42,
		}

		var out struct {
			Status   string `json:"status"`
			Received bool   `json:"received"`
		}

		err := group.Post(context.Background(), "/create", query, reqPayload, &out)
		if err != nil {
			t.Fatalf("Post failed: %v", err)
		}

		if rec.method != http.MethodPost {
			t.Errorf("method = %s, want POST", rec.method)
		}
		if rec.path != "/api/v1/test/create" {
			t.Errorf("path = %s, want /api/v1/test/create", rec.path)
		}
		if rec.query.Get("dry_run") != "true" {
			t.Errorf("unexpected query: %v", rec.query)
		}
		if rec.headers.Get("Content-Type") != "application/json" {
			t.Errorf("Content-Type = %q, want application/json", rec.headers.Get("Content-Type"))
		}
		if rec.headers.Get("X-Service-Token") != "group-token-abc" {
			t.Errorf("X-Service-Token = %q, want group-token-abc", rec.headers.Get("X-Service-Token"))
		}

		var parsedBody map[string]any
		if err := json.Unmarshal(rec.body, &parsedBody); err != nil {
			t.Fatalf("failed to parse server received body: %v", err)
		}
		if parsedBody["name"] != "test-item" || parsedBody["count"] != float64(42) {
			t.Errorf("unexpected body received: %v", parsedBody)
		}
		if !out.Received || out.Status != "success" {
			t.Errorf("unexpected output decoded: %+v", out)
		}
	})
}

func TestTransport_RouteGroupIsolation(t *testing.T) {
	type callRecord struct {
		path  string
		token string
	}
	var mu sync.Mutex
	var calls []callRecord

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		calls = append(calls, callRecord{
			path:  r.URL.Path,
			token: r.Header.Get("X-Service-Token"),
		})
		mu.Unlock()

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"status":"ok"}`)
	}))
	defer srv.Close()

	cfg := Config{
		BackendBaseURL: srv.URL,
		MaxConcurrency: 5,
		Environment:    "dev",
	}
	tr, err := NewTransport(cfg)
	if err != nil {
		t.Fatalf("NewTransport: %v", err)
	}

	groupMarket := tr.NewRouteGroup("/api/v1/market/data", "token-market-xxx")
	groupPortfolio := tr.NewRouteGroup("/api/v1/portfolio", "token-portfolio-yyy")

	if groupMarket.Prefix() != "/api/v1/market/data" {
		t.Errorf("groupMarket prefix = %s, want /api/v1/market/data", groupMarket.Prefix())
	}
	if groupMarket.Token() != "token-market-xxx" {
		t.Errorf("groupMarket token = %s, want token-market-xxx", groupMarket.Token())
	}
	if groupMarket.Transport() != tr {
		t.Errorf("groupMarket transport does not match parent transport")
	}

	if groupPortfolio.Prefix() != "/api/v1/portfolio" {
		t.Errorf("groupPortfolio prefix = %s, want /api/v1/portfolio", groupPortfolio.Prefix())
	}
	if groupPortfolio.Token() != "token-portfolio-yyy" {
		t.Errorf("groupPortfolio token = %s, want token-portfolio-yyy", groupPortfolio.Token())
	}

	var out json.RawMessage
	if err := groupMarket.Get(context.Background(), "/prices/AAPL", nil, &out); err != nil {
		t.Fatalf("groupMarket.Get failed: %v", err)
	}

	if err := groupPortfolio.Post(context.Background(), "/positions", nil, map[string]string{"sym": "AAPL"}, &out); err != nil {
		t.Fatalf("groupPortfolio.Post failed: %v", err)
	}

	mu.Lock()
	defer mu.Unlock()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d", len(calls))
	}

	if calls[0].path != "/api/v1/market/data/prices/AAPL" || calls[0].token != "token-market-xxx" {
		t.Errorf("call 0 mismatch: got path=%q, token=%q", calls[0].path, calls[0].token)
	}
	if calls[1].path != "/api/v1/portfolio/positions" || calls[1].token != "token-portfolio-yyy" {
		t.Errorf("call 1 mismatch: got path=%q, token=%q", calls[1].path, calls[1].token)
	}
}

func TestTransport_ErrorClassification(t *testing.T) {
	tests := []struct {
		name       string
		status     int
		body       string
		wantErr    error
		wantDetail string
		wantValid  string
	}{
		{
			name:       "404 not found maps to ErrNoData",
			status:     http.StatusNotFound,
			body:       `{"detail":"no data"}`,
			wantErr:    ErrNoData,
			wantDetail: `{"detail":"no data"}`,
		},
		{
			name:       "422 unprocessable maps to ErrValidation with parsed message",
			status:     http.StatusUnprocessableEntity,
			body:       `{"detail":[{"loc":["query","limit"],"msg":"greater than 0"}]}`,
			wantErr:    ErrValidation,
			wantDetail: `{"detail":[{"loc":["query","limit"],"msg":"greater than 0"}]}`,
			wantValid:  "limit greater than 0",
		},
		{
			name:       "401 unauthorized maps to ErrConfiguration",
			status:     http.StatusUnauthorized,
			body:       `{"detail":"bad token"}`,
			wantErr:    ErrConfiguration,
			wantDetail: `{"detail":"bad token"}`,
		},
		{
			name:       "403 forbidden maps to ErrConfiguration",
			status:     http.StatusForbidden,
			body:       `{"detail":"forbidden"}`,
			wantErr:    ErrConfiguration,
			wantDetail: `{"detail":"forbidden"}`,
		},
		{
			name:       "500 internal server error maps to ErrProvider",
			status:     http.StatusInternalServerError,
			body:       `backend crashed`,
			wantErr:    ErrProvider,
			wantDetail: `backend crashed`,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tc.status)
				_, _ = io.WriteString(w, tc.body)
			}))
			defer srv.Close()

			cfg := Config{
				BackendBaseURL: srv.URL,
				ServiceToken:   "token",
				MaxConcurrency: 5,
				Environment:    "prod",
			}
			tr, err := NewTransport(cfg)
			if err != nil {
				t.Fatalf("NewTransport: %v", err)
			}
			group := tr.NewRouteGroup("/test", "token")

			var out json.RawMessage
			err = group.Get(context.Background(), "/resource", nil, &out)
			if err == nil {
				t.Fatalf("expected error, got nil")
			}

			if !errors.Is(err, tc.wantErr) {
				t.Errorf("errors.Is(%v, %v) = false", err, tc.wantErr)
			}

			var bErr *backendError
			if !errors.As(err, &bErr) {
				t.Fatalf("err is not *backendError: %T", err)
			}
			if bErr.Status() != tc.status {
				t.Errorf("Status() = %d, want %d", bErr.Status(), tc.status)
			}
			if bErr.Detail() != tc.wantDetail {
				t.Errorf("Detail() = %q, want %q", bErr.Detail(), tc.wantDetail)
			}
			if tc.wantValid != "" && bErr.ValidationMessage() != tc.wantValid {
				t.Errorf("ValidationMessage() = %q, want %q", bErr.ValidationMessage(), tc.wantValid)
			}
		})
	}
}

func TestTransport_Logging(t *testing.T) {
	const secretToken = "super-secret-transport-token-999"

	t.Run("dev debug request and response logging", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "dev", "DEBUG")
		if err != nil {
			t.Fatalf("newLogger: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = io.WriteString(w, `{"result":"ok"}`)
		}))
		defer srv.Close()

		cfg := Config{
			BackendBaseURL: srv.URL,
			ServiceToken:   secretToken,
			MaxConcurrency: 5,
			Environment:    "dev",
		}
		tr, err := NewTransport(cfg)
		if err != nil {
			t.Fatalf("NewTransport: %v", err)
		}
		group := tr.NewRouteGroup("/api/test", secretToken)

		query := url.Values{}
		query.Set("q", "search-term")

		var out json.RawMessage
		if err := group.Get(context.Background(), "/items", query, &out); err != nil {
			t.Fatalf("Get error: %v", err)
		}

		logs := buf.String()
		if !strings.Contains(logs, "backend request") {
			t.Errorf("expected 'backend request' in logs, got:\n%s", logs)
		}
		if !strings.Contains(logs, "method=GET") {
			t.Errorf("expected 'method=GET' in logs, got:\n%s", logs)
		}
		if !strings.Contains(logs, "/api/test/items") {
			t.Errorf("expected endpoint path in logs, got:\n%s", logs)
		}
		if !strings.Contains(logs, "q=search-term") {
			t.Errorf("expected query params in logs, got:\n%s", logs)
		}
		if !strings.Contains(logs, "backend response") {
			t.Errorf("expected 'backend response' in logs, got:\n%s", logs)
		}
		if !strings.Contains(logs, "status=200") {
			t.Errorf("expected 'status=200' in logs, got:\n%s", logs)
		}

		// Security: token and header must never be logged
		if strings.Contains(logs, secretToken) {
			t.Fatalf("secret token was logged in dev debug logs: %s", logs)
		}
		if strings.Contains(logs, "X-Service-Token") {
			t.Fatalf("X-Service-Token header was logged in dev debug logs: %s", logs)
		}
	})

	t.Run("non-2xx error logging at ERROR level", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"not found"}`)
		}))
		defer srv.Close()

		cfg := Config{
			BackendBaseURL: srv.URL,
			ServiceToken:   secretToken,
			MaxConcurrency: 5,
			Environment:    "prod",
		}
		tr, err := NewTransport(cfg)
		if err != nil {
			t.Fatalf("NewTransport: %v", err)
		}
		group := tr.NewRouteGroup("/api/test", secretToken)

		var out json.RawMessage
		_ = group.Get(context.Background(), "/missing", nil, &out)

		logs := buf.String()
		if !strings.Contains(logs, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log, got:\n%s", logs)
		}
		if !strings.Contains(logs, `"status":404`) {
			t.Errorf("expected status:404 in logs, got:\n%s", logs)
		}
		if strings.Contains(logs, secretToken) {
			t.Fatalf("secret token was logged in error logs: %s", logs)
		}
	})
}

func TestTransport_ConcurrencyCap(t *testing.T) {
	var inFlight atomic.Int32
	var maxInFlight atomic.Int32

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cur := inFlight.Add(1)
		for {
			old := maxInFlight.Load()
			if cur <= old || maxInFlight.CompareAndSwap(old, cur) {
				break
			}
		}
		time.Sleep(20 * time.Millisecond)
		inFlight.Add(-1)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"status":"ok"}`)
	}))
	defer srv.Close()

	cfg := Config{
		BackendBaseURL: srv.URL,
		MaxConcurrency: 2,
		Environment:    "prod",
	}
	tr, err := NewTransport(cfg)
	if err != nil {
		t.Fatalf("NewTransport: %v", err)
	}

	group := tr.NewRouteGroup("/test", "token")

	const totalRequests = 10
	var wg sync.WaitGroup
	errCh := make(chan error, totalRequests)

	for i := 0; i < totalRequests; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var out json.RawMessage
			if err := group.Get(context.Background(), "/concurrent", nil, &out); err != nil {
				errCh <- err
			}
		}()
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		t.Errorf("unexpected error during concurrency test: %v", err)
	}

	observed := maxInFlight.Load()
	if observed > 2 {
		t.Errorf("max in flight was %d, want <= 2", observed)
	}
	if observed < 2 {
		t.Errorf("expected concurrency to reach 2, got %d", observed)
	}
}
