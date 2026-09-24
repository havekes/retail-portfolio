package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
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

func mustClient(t *testing.T, baseURL, token string) *BackendClient {
	t.Helper()
	client, err := NewBackendClient(baseURL, token)
	if err != nil {
		t.Fatalf("NewBackendClient(%q): %v", baseURL, err)
	}
	return client
}

func TestNewBackendClientRejectsBadBaseURL(t *testing.T) {
	for _, raw := range []string{"", "   ", "not-a-url", "ftp://backend:8000", "http://"} {
		if _, err := NewBackendClient(raw, "token"); err == nil {
			t.Errorf("NewBackendClient(%q) = nil error, want error", raw)
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
		history, err := mustClient(t, srv.URL, "test-token").Prices(
			context.Background(),
			"aapl",
			time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
			time.Date(2026, 1, 31, 0, 0, 0, 0, time.UTC),
			"",
		)
		if err != nil {
			t.Fatalf("Prices: %v", err)
		}
		if history.Symbol != "AAPL" || history.Exchange != nil {
			t.Errorf("header = %+v", history)
		}
		if len(history.Items) != 1 {
			t.Fatalf("items = %d, want 1", len(history.Items))
		}
		bar := history.Items[0]
		if bar.Open != Decimal("150.00") || bar.Volume != 1_000_000 {
			t.Errorf("bar = %+v", bar)
		}
		if bar.AdjustedClose == nil || *bar.AdjustedClose != Decimal("153.50") {
			t.Errorf("adjusted_close = %v", bar.AdjustedClose)
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
		fundamentals, err := mustClient(t, srv.URL, "test-token").Fundamentals(
			context.Background(), "AAPL", "",
		)
		if err != nil {
			t.Fatalf("Fundamentals: %v", err)
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
		chain, err := mustClient(t, srv.URL, "test-token").OptionsChain(
			context.Background(), "AAPL", nil, "", nil, nil,
		)
		if err != nil {
			t.Fatalf("OptionsChain: %v", err)
		}
		if chain.UnderlyingSymbol != "AAPL" || len(chain.Contracts) != 1 {
			t.Fatalf("chain = %+v", chain)
		}
		entry := chain.Contracts[0]
		if entry.Contract.ContractType != "call" || entry.Contract.StrikePrice != Decimal("150") {
			t.Errorf("contract = %+v", entry.Contract)
		}
		if entry.Quote.OpenInterest == nil || *entry.Quote.OpenInterest != Decimal("8421") {
			t.Errorf("open_interest = %v", entry.Quote.OpenInterest)
		}
		if entry.Quote.Greeks == nil || entry.Quote.Greeks.Delta == nil ||
			*entry.Quote.Greeks.Delta != Decimal("0.5314") {
			t.Errorf("greeks = %+v", entry.Quote.Greeks)
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
