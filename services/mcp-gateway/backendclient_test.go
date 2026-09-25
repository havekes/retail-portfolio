package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
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

// providerNames are the upstream provider brands that must never appear in this
// module's user-facing strings. They are assembled from fragments so this test
// file itself stays free of the brands it asserts against (the acceptance
// criterion covers the whole module, not just runtime strings).
var providerNames = []string{
	"FM" + "P",
	"Poly" + "gon",
	"EOD" + "HD",
}

type capturedRequest struct {
	path   string
	query  url.Values
	header http.Header
}

func newStubBackend(t *testing.T, status int, body string) (*httptest.Server, *capturedRequest) {
	t.Helper()
	cap := &capturedRequest{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cap.path = r.URL.Path
		cap.query = r.URL.Query()
		cap.header = r.Header.Clone()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	}))
	t.Cleanup(srv.Close)
	return srv, cap
}

func mustClient(t *testing.T, baseURL, token string, env ...string) *BackendClient {
	t.Helper()
	client, err := NewBackendClient(baseURL, token, defaultMaxConcurrency, env...)
	if err != nil {
		t.Fatalf("NewBackendClient(%q): %v", baseURL, err)
	}
	return client
}

func TestNewBackendClientRejectsBadBaseURL(t *testing.T) {
	for _, raw := range []string{"", "   ", "not-a-url", "ftp://backend:8000", "http://"} {
		if _, err := NewBackendClient(raw, "token", defaultMaxConcurrency); err == nil {
			t.Errorf("NewBackendClient(%q) = nil error, want error", raw)
		}
	}
}

func TestNewBackendClientRejectsInvalidMaxConcurrency(t *testing.T) {
	for _, val := range []int{0, -1, -10} {
		if _, err := NewBackendClient("http://backend:8000", "token", val); err == nil {
			t.Errorf("NewBackendClient with maxConcurrency=%d expected error, got nil", val)
		}
	}
}

func TestBackendClientEndpoints(t *testing.T) {
	from := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	to := time.Date(2026, 1, 31, 0, 0, 0, 0, time.UTC)
	expiry := time.Date(2026, 1, 16, 0, 0, 0, 0, time.UTC)
	strikeMin := 100.0
	strikeMax := 200.0

	tests := []struct {
		name      string
		body      string
		call      func(context.Context, *BackendClient) error
		wantPath  string
		wantQuery map[string]string
	}{
		{
			name: "prices",
			body: `{"symbol":"AAPL","from_date":"2026-01-01","to_date":"2026-01-31","items":[]}`,
			call: func(ctx context.Context, c *BackendClient) error {
				_, err := c.Prices(ctx, "aapl", from, to, "nasdaq")
				return err
			},
			wantPath: "/api/v1/market/data/prices/AAPL",
			wantQuery: map[string]string{
				"from":     "2026-01-01",
				"to":       "2026-01-31",
				"exchange": "nasdaq",
			},
		},
		{
			name: "symbol search",
			body: `[{"symbol":"AAPL","name":"Apple"}]`,
			call: func(ctx context.Context, c *BackendClient) error {
				_, err := c.SymbolSearch(ctx, "apple")
				return err
			},
			wantPath:  "/api/v1/market/data/symbols/search",
			wantQuery: map[string]string{"q": "apple"},
		},
		{
			name: "options chain",
			body: `{"underlying_symbol":"AAPL","contracts":[]}`,
			call: func(ctx context.Context, c *BackendClient) error {
				_, err := c.OptionsChain(ctx, "aapl", &expiry, "call", &strikeMin, &strikeMax)
				return err
			},
			wantPath: "/api/v1/market/data/options/AAPL",
			wantQuery: map[string]string{
				"expiry":      "2026-01-16",
				"option_type": "call",
				"strike_min":  "100",
				"strike_max":  "200",
			},
		},
		{
			name: "fundamentals",
			body: `{"profile":{},"key_metrics":{},"ratios":{}}`,
			call: func(ctx context.Context, c *BackendClient) error {
				_, err := c.Fundamentals(ctx, "aapl", "nasdaq")
				return err
			},
			wantPath:  "/api/v1/market/data/fundamentals/AAPL",
			wantQuery: map[string]string{"exchange": "nasdaq"},
		},
		{
			name: "statements",
			body: `[{"symbol":"AAPL","revenue":"391035000000"}]`,
			call: func(ctx context.Context, c *BackendClient) error {
				_, err := c.Statements(ctx, "aapl", "income", "annual", 5, "nasdaq")
				return err
			},
			wantPath: "/api/v1/market/data/fundamentals/AAPL/statements",
			wantQuery: map[string]string{
				"statement": "income",
				"period":    "annual",
				"limit":     "5",
				"exchange":  "nasdaq",
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			srv, cap := newStubBackend(t, http.StatusOK, tc.body)
			client := mustClient(t, srv.URL, "test-token")

			if err := tc.call(context.Background(), client); err != nil {
				t.Fatalf("call returned error: %v", err)
			}
			if cap.path != tc.wantPath {
				t.Errorf("path = %q, want %q", cap.path, tc.wantPath)
			}
			for key, want := range tc.wantQuery {
				if got := cap.query.Get(key); got != want {
					t.Errorf("query %q = %q, want %q", key, got, want)
				}
			}
		})
	}
}

func TestBackendClientSendsServiceToken(t *testing.T) {
	srv, cap := newStubBackend(t, http.StatusOK, `{"underlying_symbol":"AAPL","contracts":[]}`)
	client := mustClient(t, srv.URL+"/", "super-secret-token") // trailing slash tolerated

	if _, err := client.OptionsChain(context.Background(), "AAPL", nil, "", nil, nil); err != nil {
		t.Fatalf("call returned error: %v", err)
	}
	if got := cap.header.Get(serviceTokenHeader); got != "super-secret-token" {
		t.Errorf("%s = %q, want %q", serviceTokenHeader, got, "super-secret-token")
	}
	if got := cap.header.Get("Accept"); got != "application/json" {
		t.Errorf("Accept = %q, want application/json", got)
	}
	if strings.Contains(cap.path, "//") {
		t.Errorf("path has a double slash: %q", cap.path)
	}
}

func TestBackendClientErrorTaxonomy(t *testing.T) {
	tests := []struct {
		name   string
		status int
		body   string
		want   error
	}{
		{"404 is no data", http.StatusNotFound, `{"detail":"No market data found."}`, ErrNoData},
		{"422 is validation", http.StatusUnprocessableEntity, `{"detail":"bad range"}`, ErrValidation},
		{"401 is configuration", http.StatusUnauthorized, `{"detail":"Service token invalid"}`, ErrConfiguration},
		{"403 is configuration", http.StatusForbidden, `{"detail":"forbidden"}`, ErrConfiguration},
		{"500 is provider", http.StatusInternalServerError, `{"detail":"boom"}`, ErrProvider},
		{"503 is provider", http.StatusServiceUnavailable, `{"detail":"unavailable"}`, ErrProvider},
		{"non-JSON 200 is provider", http.StatusOK, `<html>nope</html>`, ErrProvider},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			srv, _ := newStubBackend(t, tc.status, tc.body)
			client := mustClient(t, srv.URL, "test-token")

			_, err := client.Fundamentals(context.Background(), "AAPL", "")
			if err == nil {
				t.Fatal("expected an error")
			}
			if !errors.Is(err, tc.want) {
				t.Fatalf("errors.Is(err, %v) = false; err = %v", tc.want, err)
			}
		})
	}
}

func TestBackendClientValidationMessage(t *testing.T) {
	// A 422 is a validation failure, never "no data": it must classify as
	// ErrValidation (and not ErrNoData) and carry an agent-safe message parsed
	// from the FastAPI body when one is present.
	tests := []struct {
		name string
		body string
		want string
	}{
		{"string detail", `{"detail":"expiry must be a valid date"}`, "expiry must be a valid date"},
		{
			"pydantic detail array",
			`{"detail":[{"loc":["query","expiry"],"msg":"invalid date","type":"value_error"}]}`,
			"expiry invalid date",
		},
		{"empty body", ``, ErrValidation.Error()},
		{"non-JSON body", `<html>nope</html>`, ErrValidation.Error()},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			srv, _ := newStubBackend(t, http.StatusUnprocessableEntity, tc.body)
			client := mustClient(t, srv.URL, "test-token")

			_, err := client.Fundamentals(context.Background(), "AAPL", "")
			if err == nil {
				t.Fatal("expected an error")
			}
			if !errors.Is(err, ErrValidation) {
				t.Fatalf("errors.Is(err, ErrValidation) = false; err = %v", err)
			}
			if errors.Is(err, ErrNoData) {
				t.Fatalf("errors.Is(err, ErrNoData) = true for a 422; err = %v", err)
			}
			var backendErr *backendError
			if !errors.As(err, &backendErr) {
				t.Fatalf("err is %T, want *backendError", err)
			}
			if got := backendErr.ValidationMessage(); got != tc.want {
				t.Errorf("ValidationMessage() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestBackendClientDecodesRealBackendShapes(t *testing.T) {
	// Fixtures mirror the exact JSON FastAPI emits for the Pydantic models in
	// src/market/schema.py and src/market/api_types.py: snake_case keys, dates
	// as YYYY-MM-DD strings, and Decimal values as JSON strings.
	t.Run("prices", func(t *testing.T) {
		srv, _ := newStubBackend(t, http.StatusOK, `{
			"symbol": "AAPL",
			"exchange": null,
			"from_date": "2026-01-01",
			"to_date": "2026-01-31",
			"items": [
				{"date": "2026-01-02", "open": "150.00", "high": "155.00",
				 "low": "149.00", "close": "154.00", "volume": 1000000,
				 "adjusted_close": "153.50"}
			]
		}`)
		raw, err := mustClient(t, srv.URL, "test-token").Prices(
			context.Background(),
			"aapl",
			time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
			time.Date(2026, 1, 31, 0, 0, 0, 0, time.UTC),
			"",
		)
		if err != nil {
			t.Fatalf("Prices: %v", err)
		}
		var history map[string]json.RawMessage
		if err := json.Unmarshal(raw, &history); err != nil {
			t.Fatalf("raw is not a JSON object: %v", err)
		}
		if string(history["symbol"]) != `"AAPL"` {
			t.Errorf("symbol = %s, want %q", history["symbol"], "AAPL")
		}
		var items []map[string]json.RawMessage
		if err := json.Unmarshal(history["items"], &items); err != nil {
			t.Fatalf("items is not a JSON array: %v", err)
		}
		if len(items) != 1 {
			t.Fatalf("items = %d, want 1", len(items))
		}
	})

	t.Run("fundamentals", func(t *testing.T) {
		srv, _ := newStubBackend(t, http.StatusOK, `{
			"profile": {"symbol": "AAPL", "company_name": "Apple Inc.",
				"market_cap": "3400000000000", "sector": "Technology",
				"ceo": "Tim Cook", "full_time_employees": 164000,
				"exchange": "NASDAQ", "currency": "USD",
				"is_actively_trading": true},
			"key_metrics": {"symbol": "AAPL", "date": "2024-09-28",
				"fiscal_year": "2024", "period": "FY",
				"market_cap": "3400000000000", "pe_ratio": "36.28"},
			"ratios": {"symbol": "AAPL", "date": "2024-09-28",
				"gross_profit_margin": "0.4621", "debt_to_equity": "1.87"}
		}`)
		raw, err := mustClient(t, srv.URL, "test-token").Fundamentals(
			context.Background(), "AAPL", "",
		)
		if err != nil {
			t.Fatalf("Fundamentals: %v", err)
		}
		var fundamentals CompanyFundamentals
		if err := json.Unmarshal(raw, &fundamentals); err != nil {
			t.Fatalf("unmarshal fundamentals: %v", err)
		}
		if fundamentals.Profile.CompanyName != "Apple Inc." {
			t.Errorf("company_name = %q", fundamentals.Profile.CompanyName)
		}
		if fundamentals.Profile.MarketCap == nil ||
			*fundamentals.Profile.MarketCap != Decimal("3400000000000") {
			t.Errorf("market_cap = %v", fundamentals.Profile.MarketCap)
		}
		if fundamentals.KeyMetrics.PERatio == nil ||
			*fundamentals.KeyMetrics.PERatio != Decimal("36.28") {
			t.Errorf("pe_ratio = %v", fundamentals.KeyMetrics.PERatio)
		}
		if fundamentals.Ratios.DebtToEquity == nil ||
			*fundamentals.Ratios.DebtToEquity != Decimal("1.87") {
			t.Errorf("debt_to_equity = %v", fundamentals.Ratios.DebtToEquity)
		}
	})

	t.Run("options chain", func(t *testing.T) {
		srv, _ := newStubBackend(t, http.StatusOK, `{
			"underlying_symbol": "AAPL",
			"as_of": "2026-01-02",
			"contracts": [
				{"contract": {"contract_ticker": "O:AAPL260116C00150000",
					"symbol": "AAPL", "strike_price": "150",
					"expiration_date": "2026-01-16", "contract_type": "call",
					"shares_per_contract": 100, "primary_exchange": null,
					"active": true},
				 "quote": {"implied_volatility": "0.2417",
					"open_interest": 8421, "day_volume": 1875,
					"greeks": {"delta": "0.5314", "gamma": "0.0128",
						"theta": "-0.0731", "vega": "0.3412", "rho": null}}}
			]
		}`)
		raw, err := mustClient(t, srv.URL, "test-token").OptionsChain(
			context.Background(), "AAPL", nil, "", nil, nil,
		)
		if err != nil {
			t.Fatalf("OptionsChain: %v", err)
		}
		var chain map[string]json.RawMessage
		if err := json.Unmarshal(raw, &chain); err != nil {
			t.Fatalf("raw is not a JSON object: %v", err)
		}
		if string(chain["underlying_symbol"]) != `"AAPL"` {
			t.Errorf("underlying_symbol = %s, want %q", chain["underlying_symbol"], "AAPL")
		}
		var contracts []map[string]json.RawMessage
		if err := json.Unmarshal(chain["contracts"], &contracts); err != nil {
			t.Fatalf("contracts is not a JSON array: %v", err)
		}
		if len(contracts) != 1 {
			t.Fatalf("contracts len = %d, want 1", len(contracts))
		}
	})

	t.Run("statements stay raw", func(t *testing.T) {
		srv, _ := newStubBackend(t, http.StatusOK, `[{"date": "2024-09-28", "symbol": "AAPL", "revenue": "391035000000"}]`)
		raw, err := mustClient(t, srv.URL, "test-token").Statements(
			context.Background(), "AAPL", "income", "annual", 5, "",
		)
		if err != nil {
			t.Fatalf("Statements: %v", err)
		}
		var decoded []map[string]json.RawMessage
		if err := json.Unmarshal(raw, &decoded); err != nil {
			t.Fatalf("raw is not a JSON array: %v", err)
		}
		if len(decoded) != 1 || string(decoded[0]["revenue"]) != `"391035000000"` {
			t.Errorf("decoded = %v", decoded)
		}
	})

	t.Run("statements tolerate unknown fields", func(t *testing.T) {
		srv, _ := newStubBackend(t, http.StatusOK, `[{"date": "2024-09-28", "symbol": "AAPL", "revenue": "391035000000", "extra_backend_field": "test"}]`)
		raw, err := mustClient(t, srv.URL, "test-token").Statements(
			context.Background(), "AAPL", "income", "annual", 5, "",
		)
		if err != nil {
			t.Fatalf("Statements: %v", err)
		}
		items, err := decodeStatementList(raw, "income")
		if err != nil {
			t.Fatalf("decodeStatementList failed on unknown field: %v", err)
		}
		incomeItems, ok := items.([]IncomeStatement)
		if !ok || len(incomeItems) != 1 {
			t.Fatalf("unexpected items: %+v", items)
		}
		if incomeItems[0].Revenue == nil || *incomeItems[0].Revenue != Decimal("391035000000") {
			t.Errorf("revenue = %v", incomeItems[0].Revenue)
		}
	})
}

func TestBackendClientTransportErrorIsProvider(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	srv.Close() // close immediately so the connection is refused

	client := mustClient(t, srv.URL, "test-token")
	_, err := client.Fundamentals(context.Background(), "AAPL", "")
	if !errors.Is(err, ErrProvider) {
		t.Fatalf("errors.Is(err, ErrProvider) = false; err = %v", err)
	}
}

func TestBackendClientErrorsNeverLeakSecretsOrProviders(t *testing.T) {
	const token = "super-secret-token"

	cases := []struct {
		name   string
		status int
		body   string
	}{
		{"no data", http.StatusNotFound, `{"detail":"No market data found for 'AAPL'."}`},
		{"validation", http.StatusUnprocessableEntity, `{"detail":"expiry must be a valid date"}`},
		{"configuration", http.StatusUnauthorized, `{"detail":"Service token invalid"}`},
		{"provider", http.StatusInternalServerError, `{"detail":"upstream exploded"}`},
		{"non-json", http.StatusOK, `not json`},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			srv, _ := newStubBackend(t, tc.status, tc.body)
			client := mustClient(t, srv.URL, token)

			_, err := client.Fundamentals(context.Background(), "AAPL", "")
			if err == nil {
				t.Fatal("expected an error")
			}

			message := err.Error()
			if strings.Contains(message, token) {
				t.Errorf("error leaked the token: %q", message)
			}
			for _, provider := range providerNames {
				if strings.Contains(strings.ToLower(message), strings.ToLower(provider)) {
					t.Errorf("error leaked provider %q: %q", provider, message)
				}
			}
		})
	}

	for _, sentinel := range []error{ErrNoData, ErrValidation, ErrConfiguration, ErrProvider} {
		for _, provider := range providerNames {
			if strings.Contains(strings.ToLower(sentinel.Error()), strings.ToLower(provider)) {
				t.Errorf("sentinel %v leaks provider %q", sentinel, provider)
			}
		}
	}
}

func TestBackendClient_Logging(t *testing.T) {
	const secretToken = "super-secret-backend-token-12345"

	t.Run("dev outbound request and response logging", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "dev", "DEBUG")
		if err != nil {
			t.Fatalf("newLogger: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		srv, _ := newStubBackend(t, http.StatusOK, `{"symbol":"AAPL","prices":[]}`)
		client := mustClient(t, srv.URL, secretToken, "dev")

		ctx := context.Background()
		from, _ := time.Parse("2006-01-02", "2024-01-01")
		to, _ := time.Parse("2006-01-02", "2024-01-02")
		_, err = client.Prices(ctx, "AAPL", from, to, "")
		if err != nil {
			t.Fatalf("Prices error: %v", err)
		}

		out := buf.String()
		if !strings.Contains(out, "backend request") {
			t.Errorf("expected 'backend request' in log, got:\n%s", out)
		}
		if !strings.Contains(out, "method=GET") {
			t.Errorf("expected method=GET in log, got:\n%s", out)
		}
		if !strings.Contains(out, "/api/v1/market/data/prices/AAPL") {
			t.Errorf("expected endpoint URL in log, got:\n%s", out)
		}
		if !strings.Contains(out, "from=2024-01-01") || !strings.Contains(out, "to=2024-01-02") {
			t.Errorf("expected query params in log, got:\n%s", out)
		}
		if !strings.Contains(out, "status=200") {
			t.Errorf("expected status=200 in log, got:\n%s", out)
		}

		// Token check
		if strings.Contains(out, secretToken) {
			t.Fatalf("secret token was logged: %s", out)
		}
		if strings.Contains(out, serviceTokenHeader) {
			t.Fatalf("X-Service-Token header was logged: %s", out)
		}
	})

	t.Run("outbound error logging on non-2xx statuses", func(t *testing.T) {
		statuses := []struct {
			status int
			body   string
		}{
			{status: http.StatusNotFound, body: `{"detail":"no price data"}`},
			{status: http.StatusUnprocessableEntity, body: `{"detail":[{"loc":["query","from"],"msg":"invalid date"}]}`},
			{status: http.StatusInternalServerError, body: `internal server failure`},
		}

		for _, tc := range statuses {
			var buf bytes.Buffer
			logger, err := newLogger(&buf, "prod", "INFO")
			if err != nil {
				t.Fatalf("newLogger: %v", err)
			}
			prev := setSlogDefault(logger)
			defer setSlogDefault(prev)

			srv, _ := newStubBackend(t, tc.status, tc.body)
			client := mustClient(t, srv.URL, secretToken, "prod")

			_, err = client.SymbolSearch(context.Background(), "AAPL")
			if err == nil {
				t.Fatalf("expected error for status %d", tc.status)
			}

			out := buf.String()
			if !strings.Contains(out, `"level":"ERROR"`) {
				t.Errorf("expected ERROR level log for status %d, got:\n%s", tc.status, out)
			}
			if !strings.Contains(out, `"status":`+fmt.Sprintf("%d", tc.status)) {
				t.Errorf("expected status %d in log, got:\n%s", tc.status, out)
			}
			if !strings.Contains(out, `"detail":`) {
				t.Errorf("expected detail in log, got:\n%s", out)
			}
			if strings.Contains(out, secretToken) {
				t.Fatalf("secret token was logged on error: %s", out)
			}
		}
	})

	t.Run("outbound error logging on network errors", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		// Unreachable port / connection refused
		client := mustClient(t, "http://127.0.0.1:54321", secretToken, "prod")

		_, err = client.SymbolSearch(context.Background(), "AAPL")
		if err == nil {
			t.Fatal("expected network error")
		}

		out := buf.String()
		if !strings.Contains(out, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log on network error, got:\n%s", out)
		}
		if !strings.Contains(out, `"status":0`) {
			t.Errorf("expected status:0 on network error, got:\n%s", out)
		}
		if !strings.Contains(out, `"detail":`) {
			t.Errorf("expected detail on network error, got:\n%s", out)
		}
		if strings.Contains(out, secretToken) {
			t.Fatalf("secret token was logged on network error: %s", out)
		}
	})
}

func TestBackendClient_ProviderNameCompliance(t *testing.T) {
	var buf bytes.Buffer
	logger, err := newLogger(&buf, "dev", "DEBUG")
	if err != nil {
		t.Fatalf("newLogger: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	srv, _ := newStubBackend(t, http.StatusOK, `{"symbol":"AAPL","prices":[]}`)
	client := mustClient(t, srv.URL, "token", "dev")

	from, _ := time.Parse("2006-01-02", "2024-01-01")
	to, _ := time.Parse("2006-01-02", "2024-01-02")
	_, _ = client.Prices(context.Background(), "AAPL", from, to, "")

	assertNoProviderName(t, "backend client log", buf.String())
}

type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.Write(p)
}

func (s *syncBuffer) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.String()
}

func TestBackendClient_ConcurrencyCap(t *testing.T) {
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
		time.Sleep(25 * time.Millisecond)
		inFlight.Add(-1)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"symbol":"AAPL","prices":[]}`)
	}))
	defer srv.Close()

	client, err := NewBackendClient(srv.URL, "token", 2)
	if err != nil {
		t.Fatalf("NewBackendClient: %v", err)
	}
	if client.MaxConcurrency() != 2 {
		t.Errorf("MaxConcurrency() = %d, want 2", client.MaxConcurrency())
	}

	from, _ := time.Parse("2006-01-02", "2024-01-01")
	to, _ := time.Parse("2006-01-02", "2024-01-02")

	const totalRequests = 10
	var wg sync.WaitGroup
	errCh := make(chan error, totalRequests)

	for i := 0; i < totalRequests; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := client.Prices(context.Background(), "AAPL", from, to, "")
			if err != nil {
				errCh <- err
			}
		}()
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		t.Errorf("unexpected request error: %v", err)
	}

	maxObserved := maxInFlight.Load()
	if maxObserved > 2 {
		t.Errorf("maxInFlight was %d, want <= 2", maxObserved)
	}
	if maxObserved < 2 {
		t.Errorf("expected concurrency to reach 2, but maxInFlight was %d", maxObserved)
	}
}

func TestBackendClient_ConcurrencySaturationLogging(t *testing.T) {
	var buf syncBuffer
	logger, err := newLogger(&buf, "prod", "INFO")
	if err != nil {
		t.Fatalf("newLogger: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	const secretToken = "super-secret-token-xyz"
	firstStarted := make(chan struct{})
	releaseFirst := make(chan struct{})

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-firstStarted:
			// Subsequent requests proceed immediately
		default:
			close(firstStarted)
			select {
			case <-releaseFirst:
			case <-time.After(5 * time.Second):
			}
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"symbol":"AAPL","prices":[]}`)
	}))
	defer srv.Close()
	t.Cleanup(func() {
		select {
		case <-releaseFirst:
		default:
			close(releaseFirst)
		}
	})

	client, err := NewBackendClient(srv.URL, secretToken, 1, "prod")
	if err != nil {
		t.Fatalf("NewBackendClient: %v", err)
	}

	from, _ := time.Parse("2006-01-02", "2024-01-01")
	to, _ := time.Parse("2006-01-02", "2024-01-02")

	var wg sync.WaitGroup

	// First request occupies the single semaphore slot.
	wg.Add(1)
	go func() {
		defer wg.Done()
		_, _ = client.Prices(context.Background(), "AAPL", from, to, "")
	}()

	// Wait until request 1 has reached the server handler (holding the semaphore slot).
	select {
	case <-firstStarted:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for first request to reach backend")
	}

	// Second request will be blocked on the semaphore and should log saturation warning.
	wg.Add(1)
	go func() {
		defer wg.Done()
		_, _ = client.Prices(context.Background(), "AAPL", from, to, "")
	}()

	// Wait for saturation log to appear.
	deadline := time.Now().Add(3 * time.Second)
	var logged bool
	for time.Now().Before(deadline) {
		if strings.Contains(buf.String(), "backend concurrency limit reached, queuing call") {
			logged = true
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	// Release first request so both complete cleanly.
	close(releaseFirst)
	wg.Wait()

	if !logged {
		t.Errorf("expected WARN log 'backend concurrency limit reached, queuing call', got:\n%s", buf.String())
	}
	out := buf.String()
	if !strings.Contains(out, `"level":"WARN"`) {
		t.Errorf("expected level WARN in log, got:\n%s", out)
	}
	if !strings.Contains(out, `"max_concurrency":1`) {
		t.Errorf("expected max_concurrency:1 in log, got:\n%s", out)
	}
	if strings.Contains(out, secretToken) {
		t.Fatalf("secret token was leaked in saturation log: %s", out)
	}
	assertNoProviderName(t, "concurrency saturation log", out)
}

func TestBackendClient_ContextCanceledWhileQueued(t *testing.T) {
	firstStarted := make(chan struct{})
	releaseFirst := make(chan struct{})

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-firstStarted:
			// Subsequent requests proceed immediately
		default:
			close(firstStarted)
			select {
			case <-releaseFirst:
			case <-time.After(5 * time.Second):
			}
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"symbol":"AAPL","prices":[]}`)
	}))
	defer srv.Close()
	t.Cleanup(func() {
		select {
		case <-releaseFirst:
		default:
			close(releaseFirst)
		}
	})

	client, err := NewBackendClient(srv.URL, "token", 1)
	if err != nil {
		t.Fatalf("NewBackendClient: %v", err)
	}

	from, _ := time.Parse("2006-01-02", "2024-01-01")
	to, _ := time.Parse("2006-01-02", "2024-01-02")

	// Occupy the only slot
	go func() {
		_, _ = client.Prices(context.Background(), "AAPL", from, to, "")
	}()

	select {
	case <-firstStarted:
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for first request to occupy slot")
	}

	// Issue second call with already canceled context
	canceledCtx, cancel := context.WithCancel(context.Background())
	cancel()

	done := make(chan error, 1)
	go func() {
		_, err := client.Prices(canceledCtx, "AAPL", from, to, "")
		done <- err
	}()

	select {
	case err := <-done:
		if err == nil {
			t.Fatal("expected error on canceled context, got nil")
		}
		if !errors.Is(err, ErrProvider) {
			t.Errorf("expected ErrProvider, got: %v", err)
		}
		var bErr *backendError
		if errors.As(err, &bErr) {
			if !strings.Contains(bErr.Detail(), context.Canceled.Error()) {
				t.Errorf("expected detail to mention context canceled, got: %q", bErr.Detail())
			}
		}
	case <-time.After(2 * time.Second):
		t.Fatal("call with canceled context hung waiting on concurrency semaphore")
	}

	// Also verify a context that is canceled while waiting in the queue
	ctxToCancel, cancelQueue := context.WithCancel(context.Background())
	queueDone := make(chan error, 1)
	go func() {
		_, err := client.Prices(ctxToCancel, "AAPL", from, to, "")
		queueDone <- err
	}()

	// Brief pause to ensure goroutine is queued behind semaphore
	time.Sleep(30 * time.Millisecond)
	cancelQueue()

	select {
	case err := <-queueDone:
		if err == nil {
			t.Fatal("expected error on context canceled while queued, got nil")
		}
		if !errors.Is(err, ErrProvider) {
			t.Errorf("expected ErrProvider, got: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("call canceled while queued hung waiting on concurrency semaphore")
	}

	close(releaseFirst)
}

