package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// expectedToolNames is the exact, provider-agnostic tool set this ticket
// registers. Order is irrelevant; tests compare as a set.
var expectedToolNames = []string{
	"get_price_history",
	"get_quote",
	"get_fundamentals",
	"get_options_chain",
	"get_option_expirations",
	"get_financial_statements",
	"resolve_symbol",
	"get_technical_indicator",
}

// assertNoProviderName fails if text mentions an upstream provider brand.
func assertNoProviderName(t *testing.T, label, text string) {
	t.Helper()
	for _, provider := range providerNames {
		if strings.Contains(strings.ToLower(text), strings.ToLower(provider)) {
			t.Errorf("%s leaked provider %q: %q", label, provider, text)
		}
	}
}

// newTestSession wires a stub backend through the real client and MCP router
// and returns a connected SDK client session.
func newTestSession(t *testing.T, backendURL string) *mcp.ClientSession {
	t.Helper()
	client := mustClient(t, backendURL, "test-token")
	cfg := Config{Environment: "dev"}
	srv := httptest.NewServer(newRouter(newMCPServer(client, cfg), cfg))
	t.Cleanup(srv.Close)

	mcpClient := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.1"}, nil)
	session, err := mcpClient.Connect(context.Background(), &mcp.StreamableClientTransport{
		Endpoint:             srv.URL + "/mcp",
		DisableStandaloneSSE: true,
	}, nil)
	if err != nil {
		t.Fatalf("connect to /mcp: %v", err)
	}
	t.Cleanup(func() { _ = session.Close() })
	return session
}

func callTool(t *testing.T, session *mcp.ClientSession, name string, args map[string]any) *mcp.CallToolResult {
	t.Helper()
	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      name,
		Arguments: args,
	})
	if err != nil {
		t.Fatalf("CallTool(%s): %v", name, err)
	}
	return result
}

func resultText(t *testing.T, result *mcp.CallToolResult) string {
	t.Helper()
	if len(result.Content) == 0 {
		t.Fatalf("tool result has no content: %+v", result)
	}
	text, ok := result.Content[0].(*mcp.TextContent)
	if !ok {
		t.Fatalf("tool result content is %T, want *mcp.TextContent", result.Content[0])
	}
	return text.Text
}

// Backend fixtures reuse the shapes the client's own tests assert against.
const (
	priceHistoryBody = `{
		"symbol": "AAPL", "exchange": "NASDAQ",
		"from_date": "2026-01-01", "to_date": "2026-01-31",
		"items": [{"date": "2026-01-02", "open": "150", "high": "155",
			"low": "149", "close": "154", "volume": 1000000, "adjusted_close": "153.5"}]
	}`

	quoteBody = `{
		"symbol": "AAPL", "price": "229.87", "change": "1.21",
		"change_percent": "0.528", "previous_close": "228.66",
		"open": "228.50", "day_high": "231.45", "day_low": "228.10",
		"volume": 48231900, "timestamp": "2026-04-01T14:30:00Z",
		"currency": "USD"
	}`

	fundamentalsBody = `{
		"profile": {"symbol": "AAPL", "company_name": "Apple Inc.",
			"market_cap": "3400000000000", "sector": "Technology"},
		"key_metrics": {"symbol": "AAPL", "date": "2024-09-28", "pe_ratio": "36.28"},
		"ratios": {"symbol": "AAPL", "date": "2024-09-28", "debt_to_equity": "1.87"}
	}`

	optionsChainBody = `{
		"underlying_symbol": "AAPL", "as_of": "2026-01-02",
		"contracts": [{
			"contract": {"contract_ticker": "O:AAPL260116C00150000", "symbol": "AAPL",
				"strike_price": "150", "expiration_date": "2026-01-16",
				"contract_type": "call", "shares_per_contract": 100, "active": true},
			"quote": {"implied_volatility": "0.24", "open_interest": "8421"}
		}],
		"truncated": false
	}`

	optionExpirationsBody = `{"underlying_symbol": "AAPL", "expirations": ["2026-01-16"], "truncated": false}`

	symbolSearchBody = `[{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}]`

	incomeStatementBody   = `[{"date": "2024-09-28", "symbol": "AAPL", "revenue": "391035000000"}]`
	balanceSheetBody      = `[{"date": "2024-09-28", "symbol": "AAPL", "total_assets": "364980000000"}]`
	cashFlowStatementBody = `[{"date": "2024-09-28", "symbol": "AAPL", "operating_cash_flow": "118254000000"}]`

	technicalIndicatorBody = `{
		"symbol": "AAPL", "indicator": "rsi", "currency": "USD",
		"from_date": "2026-01-01", "to_date": "2026-01-31",
		"params": {"period": 14},
		"points": [{"time": "2026-01-02", "value": 55.0, "rsi": 55.0}]
	}`
)

// toolCall is a valid invocation of one tool.
type toolCall struct {
	tool string
	args map[string]any
}

var validToolCalls = []toolCall{
	{"get_price_history", map[string]any{"symbol": "AAPL", "from": "2026-01-01", "to": "2026-01-31"}},
	{"get_quote", map[string]any{"symbol": "AAPL"}},
	{"get_fundamentals", map[string]any{"symbol": "AAPL"}},
	{"get_options_chain", map[string]any{"symbol": "AAPL", "expiry": "2026-01-16"}},
	{"get_option_expirations", map[string]any{"symbol": "AAPL"}},
	{"get_financial_statements", map[string]any{"symbol": "AAPL", "statement": "income"}},
	{"resolve_symbol", map[string]any{"query": "apple"}},
	{"get_technical_indicator", map[string]any{"symbol": "AAPL", "indicator": "rsi"}},
}

// resolveSymbolPayload is the decoded shape of the resolve_symbol tool result.
type resolveSymbolPayload struct {
	BestMatch    map[string]any   `json:"best_match"`
	Alternatives []map[string]any `json:"alternatives"`
}

// statementPayload is the decoded shape of the statement tools' envelope.
type statementPayload struct {
	Statement string                       `json:"statement"`
	Symbol    string                       `json:"symbol"`
	Period    string                       `json:"period"`
	Limit     int                          `json:"limit"`
	Exchange  string                       `json:"exchange"`
	Items     []map[string]json.RawMessage `json:"items"`
}

func TestToolsCallBackendAndReturnData(t *testing.T) {
	tests := []struct {
		name      string
		tool      string
		args      map[string]any
		body      string
		wantPath  string
		wantQuery map[string]string
		assert    func(t *testing.T, raw string)
	}{
		{
			name:     "get_price_history",
			tool:     "get_price_history",
			args:     map[string]any{"symbol": "aapl", "from": "2026-01-01", "to": "2026-01-31", "exchange": "nasdaq"},
			body:     priceHistoryBody,
			wantPath: "/api/v1/market/data/prices/AAPL",
			wantQuery: map[string]string{
				"from": "2026-01-01", "to": "2026-01-31", "exchange": "NASDAQ",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					Symbol string `json:"symbol"`
					Items  []struct {
						Close string `json:"close"`
					} `json:"items"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode PriceHistory: %v", err)
				}
				if got.Symbol != "AAPL" || len(got.Items) != 1 || got.Items[0].Close != "154" {
					t.Errorf("payload = %+v", got)
				}
			},
		},
		{
			name:     "get_quote",
			tool:     "get_quote",
			args:     map[string]any{"symbol": "aapl", "exchange": "nasdaq"},
			body:     quoteBody,
			wantPath: "/api/v1/market/data/quote/AAPL",
			wantQuery: map[string]string{
				"exchange": "NASDAQ",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					Symbol   string `json:"symbol"`
					Price    string `json:"price"`
					Currency string `json:"currency"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode Quote: %v", err)
				}
				if got.Symbol != "AAPL" || got.Price != "229.87" || got.Currency != "USD" {
					t.Errorf("payload = %+v", got)
				}
			},
		},
		{
			name:      "get_fundamentals",
			tool:      "get_fundamentals",
			args:      map[string]any{"symbol": "aapl", "exchange": "nasdaq"},
			body:      fundamentalsBody,
			wantPath:  "/api/v1/market/data/fundamentals/AAPL",
			wantQuery: map[string]string{"exchange": "NASDAQ"},
			assert: func(t *testing.T, raw string) {
				var got struct {
					Profile struct {
						CompanyName string `json:"company_name"`
					} `json:"profile"`
					KeyMetrics struct {
						PERatio *string `json:"pe_ratio"`
					} `json:"key_metrics"`
					Ratios struct {
						DebtToEquity *string `json:"debt_to_equity"`
					} `json:"ratios"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode CompanyFundamentals: %v", err)
				}
				if got.Profile.CompanyName != "Apple Inc." {
					t.Errorf("company_name = %q", got.Profile.CompanyName)
				}
				if got.KeyMetrics.PERatio == nil || *got.KeyMetrics.PERatio != "36.28" {
					t.Errorf("pe_ratio = %v", got.KeyMetrics.PERatio)
				}
				if got.Ratios.DebtToEquity == nil || *got.Ratios.DebtToEquity != "1.87" {
					t.Errorf("debt_to_equity = %v", got.Ratios.DebtToEquity)
				}
			},
		},
		{
			name: "get_options_chain",
			tool: "get_options_chain",
			args: map[string]any{
				"symbol": "aapl", "expiry": "2026-01-16", "option_type": "call",
				"strike_min": 100.0, "strike_max": 200.0,
			},
			body:     optionsChainBody,
			wantPath: "/api/v1/market/data/options/AAPL",
			wantQuery: map[string]string{
				"expiry": "2026-01-16", "option_type": "call", "strike_min": "100", "strike_max": "200",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					UnderlyingSymbol string `json:"underlying_symbol"`
					Contracts        []any  `json:"contracts"`
					Truncated        bool   `json:"truncated"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode OptionsChain: %v", err)
				}
				if got.UnderlyingSymbol != "AAPL" || len(got.Contracts) != 1 {
					t.Errorf("payload = %+v", got)
				}
				if got.Truncated {
					t.Errorf("truncated = %v, want false", got.Truncated)
				}
			},
		},
		{
			name: "get_options_chain with truncated true",
			tool: "get_options_chain",
			args: map[string]any{
				"symbol": "aapl", "expiry": "2026-01-16",
			},
			body:     `{"underlying_symbol":"AAPL","contracts":[],"truncated":true}`,
			wantPath: "/api/v1/market/data/options/AAPL",
			wantQuery: map[string]string{
				"expiry": "2026-01-16",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					UnderlyingSymbol string `json:"underlying_symbol"`
					Truncated        bool   `json:"truncated"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode OptionsChain: %v", err)
				}
				if got.UnderlyingSymbol != "AAPL" || !got.Truncated {
					t.Errorf("payload = %+v, want truncated true", got)
				}
			},
		},
		{
			name:      "get_option_expirations",
			tool:      "get_option_expirations",
			args:      map[string]any{"symbol": "aapl"},
			body:      optionExpirationsBody,
			wantPath:  "/api/v1/market/data/options/AAPL/expirations",
			wantQuery: nil,
			assert: func(t *testing.T, raw string) {
				var got struct {
					UnderlyingSymbol string   `json:"underlying_symbol"`
					Expirations      []string `json:"expirations"`
					Truncated        bool     `json:"truncated"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode OptionExpirations: %v", err)
				}
				if got.UnderlyingSymbol != "AAPL" || len(got.Expirations) != 1 || got.Expirations[0] != "2026-01-16" || got.Truncated {
					t.Errorf("payload = %+v", got)
				}
			},
		},
		{
			name:     "get_financial_statements income",
			tool:     "get_financial_statements",
			args:     map[string]any{"symbol": "aapl", "statement": "income", "period": "quarter", "limit": 3, "exchange": "nasdaq"},
			body:     incomeStatementBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL/statements",
			wantQuery: map[string]string{
				"statement": "income", "period": "quarter", "limit": "3", "exchange": "NASDAQ",
			},
			assert: func(t *testing.T, raw string) {
				var got statementPayload
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode statement envelope: %v", err)
				}
				if got.Statement != "income" || got.Symbol != "aapl" || got.Period != "quarter" || got.Limit != 3 || got.Exchange != "NASDAQ" {
					t.Errorf("envelope = %+v", got)
				}
				if len(got.Items) != 1 || string(got.Items[0]["revenue"]) != `"391035000000"` {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_financial_statements balance defaults",
			tool:     "get_financial_statements",
			args:     map[string]any{"symbol": "aapl", "statement": "balance"},
			body:     balanceSheetBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL/statements",
			wantQuery: map[string]string{
				"statement": "balance", "period": "annual", "limit": "5",
			},
			assert: func(t *testing.T, raw string) {
				var got statementPayload
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode statement envelope: %v", err)
				}
				if got.Statement != "balance" || got.Period != "annual" || got.Limit != 5 {
					t.Errorf("envelope = %+v", got)
				}
				if len(got.Items) != 1 || string(got.Items[0]["total_assets"]) != `"364980000000"` {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_financial_statements cashflow clamps limit",
			tool:     "get_financial_statements",
			args:     map[string]any{"symbol": "aapl", "statement": "cashflow", "limit": 25},
			body:     cashFlowStatementBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL/statements",
			wantQuery: map[string]string{
				"statement": "cashflow", "period": "annual", "limit": "20",
			},
			assert: func(t *testing.T, raw string) {
				var got statementPayload
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode statement envelope: %v", err)
				}
				if got.Statement != "cashflow" || got.Limit != 20 {
					t.Errorf("envelope = %+v", got)
				}
				if len(got.Items) != 1 || string(got.Items[0]["operating_cash_flow"]) != `"118254000000"` {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_fundamentals with sections",
			tool:     "get_fundamentals",
			args:     map[string]any{"symbol": "aapl", "sections": []string{"ratios"}},
			body:     fundamentalsBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL",
			assert: func(t *testing.T, raw string) {
				var got map[string]json.RawMessage
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode fundamentals: %v", err)
				}
				if len(got) != 1 {
					t.Errorf("got %d keys, want 1: %+v", len(got), got)
				}
				if _, ok := got["ratios"]; !ok {
					t.Errorf("missing ratios key: %+v", got)
				}
			},
		},
		{
			name:      "resolve_symbol",
			tool:      "resolve_symbol",
			args:      map[string]any{"query": "apple"},
			body:      symbolSearchBody,
			wantPath:  "/api/v1/market/data/symbols/search",
			wantQuery: map[string]string{"q": "apple"},
			assert: func(t *testing.T, raw string) {
				var got resolveSymbolPayload
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode resolve results: %v", err)
				}
				if got.BestMatch["symbol"] != "AAPL" {
					t.Errorf("best match = %+v", got.BestMatch)
				}
				if len(got.Alternatives) != 0 {
					t.Errorf("alternatives = %+v", got.Alternatives)
				}
			},
		},
		{
			name: "get_technical_indicator",
			tool: "get_technical_indicator",
			args: map[string]any{
				"symbol":    "aapl",
				"indicator": "bollinger",
				"period":    20,
				"std_dev":   2.0,
				"from":      "2026-01-01",
				"to":        "2026-01-31",
				"exchange":  "nasdaq",
			},
			body:     technicalIndicatorBody,
			wantPath: "/api/v1/market/data/indicators/AAPL",
			wantQuery: map[string]string{
				"indicator": "bollinger",
				"period":    "20",
				"std_dev":   "2",
				"from":      "2026-01-01",
				"to":        "2026-01-31",
				"exchange":  "NASDAQ",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					Symbol    string `json:"symbol"`
					Indicator string `json:"indicator"`
					Currency  string `json:"currency"`
					Points    []struct {
						Time  string  `json:"time"`
						Value float64 `json:"value"`
					} `json:"points"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode TechnicalIndicator: %v", err)
				}
				if got.Symbol != "AAPL" || got.Indicator != "rsi" || len(got.Points) != 1 || got.Points[0].Value != 55.0 {
					t.Errorf("payload = %+v", got)
				}
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			backend, captured := newStubBackend(t, http.StatusOK, tc.body)
			session := newTestSession(t, backend.URL)

			result := callTool(t, session, tc.tool, tc.args)
			if result.IsError {
				t.Fatalf("tool returned an error result: %s", resultText(t, result))
			}
			if captured.path != tc.wantPath {
				t.Errorf("path = %q, want %q", captured.path, tc.wantPath)
			}
			for key, want := range tc.wantQuery {
				if got := captured.query.Get(key); got != want {
					t.Errorf("query %q = %q, want %q", key, got, want)
				}
			}
			if len(tc.wantQuery) == 0 {
				// The fundamentals projections must not invent query params.
				if captured.query.Encode() != "" {
					t.Errorf("unexpected query = %q", captured.query.Encode())
				}
			}

			raw := resultText(t, result)
			assertNoProviderName(t, "tool result", raw)
			tc.assert(t, raw)
		})
	}
}

func TestRemovedToolsNotRegistered(t *testing.T) {
	srv := httptest.NewServer(newTestRouter(t))
	t.Cleanup(srv.Close)

	ctx := context.Background()
	client := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.1"}, nil)
	session, err := client.Connect(ctx, &mcp.StreamableClientTransport{
		Endpoint:             srv.URL + "/mcp",
		DisableStandaloneSSE: true,
	}, nil)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	t.Cleanup(func() { _ = session.Close() })

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		t.Fatalf("tools/list: %v", err)
	}

	registeredNames := make(map[string]bool)
	for _, tool := range tools.Tools {
		registeredNames[tool.Name] = true
	}

	// Must contain get_fundamentals, get_financial_statements, and resolve_symbol
	if !registeredNames["get_fundamentals"] {
		t.Errorf("get_fundamentals is not registered")
	}
	if !registeredNames["get_financial_statements"] {
		t.Errorf("get_financial_statements is not registered")
	}
	if !registeredNames["resolve_symbol"] {
		t.Errorf("resolve_symbol is not registered")
	}

	// Must NOT contain any of the seven removed tools
	removed := []string{
		"get_key_metrics",
		"get_financial_ratios",
		"get_company_details",
		"get_income_statement",
		"get_balance_sheet",
		"get_cash_flow_statement",
		"search_symbols",
	}
	for _, rem := range removed {
		if registeredNames[rem] {
			t.Errorf("removed tool %q is still registered", rem)
		}
	}
}

func TestToolsMapBackendErrors(t *testing.T) {
	cases := []struct {
		name     string
		status   int
		body     string
		wantErr  bool
		wantText string
	}{
		{"404 is no data", http.StatusNotFound, `{"detail":"No market data found for 'AAPL'."}`, false, noDataMessage},
		{
			"422 is validation",
			http.StatusUnprocessableEntity,
			`{"detail":[{"loc":["query","expiry"],"msg":"invalid date","type":"value_error"}]}`,
			true,
			"expiry invalid date",
		},
		{"401 is configuration", http.StatusUnauthorized, `{"detail":"Service token invalid"}`, true, ErrConfiguration.Error()},
		{"403 is configuration", http.StatusForbidden, `{"detail":"forbidden"}`, true, ErrConfiguration.Error()},
		{"500 is provider", http.StatusInternalServerError, `{"detail":"upstream exploded"}`, true, ErrProvider.Error()},
		{"503 is provider", http.StatusServiceUnavailable, `{"detail":"unavailable"}`, true, ErrProvider.Error()},
		{"non-json 200 is provider", http.StatusOK, `not json`, true, ErrProvider.Error()},
	}

	for _, tc := range validToolCalls {
		for _, errCase := range cases {
			t.Run(tc.tool+"/"+errCase.name, func(t *testing.T) {
				backend, _ := newStubBackend(t, errCase.status, errCase.body)
				session := newTestSession(t, backend.URL)

				result := callTool(t, session, tc.tool, tc.args)
				if result.IsError != errCase.wantErr {
					t.Fatalf("IsError = %v, want %v (text %q)", result.IsError, errCase.wantErr, resultText(t, result))
				}
				text := resultText(t, result)
				if text != errCase.wantText {
					t.Errorf("result text = %q, want %q", text, errCase.wantText)
				}
				assertNoProviderName(t, "tool result", text)
				for _, leak := range []string{"upstream exploded", "Service token invalid", "forbidden", "test-token"} {
					if strings.Contains(text, leak) {
						t.Errorf("result leaked backend detail %q: %q", leak, text)
					}
				}
			})
		}
	}
}

func TestToolsRejectInvalidInput(t *testing.T) {
	tests := []struct {
		name    string
		prepare func() error
		want    string
	}{
		{
			name: "symbol required",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "   "}).prepare()
				return err
			},
			want: "symbol is required",
		},
		{
			name: "symbol too long",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: strings.Repeat("A", maxSymbolLength+1)}).prepare()
				return err
			},
			want: "symbol must be at most 32 characters",
		},
		{
			name: "symbol with slash",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "AAPL/EXPIRATIONS"}).prepare()
				return err
			},
			want: `invalid symbol "AAPL/EXPIRATIONS"`,
		},
		{
			name: "symbol with url encoding",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "A%2FB"}).prepare()
				return err
			},
			want: `invalid symbol "A%2FB"`,
		},
		{
			name: "symbol dots only",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: ".."}).prepare()
				return err
			},
			want: `invalid symbol ".."`,
		},
		{
			name: "symbol with space",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "BRK B"}).prepare()
				return err
			},
			want: `invalid symbol "BRK B"`,
		},
		{
			name: "symbol with newline",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "AAPL\n"}).prepare()
				return err
			},
			want: "invalid symbol \"AAPL\\n\"",
		},
		{
			name: "symbol with caret only",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "^"}).prepare()
				return err
			},
			want: `invalid symbol "^"`,
		},
		{
			name: "bad from date",
			prepare: func() error {
				_, err := (priceHistoryInput{Symbol: "AAPL", From: "01/01/2026", To: "2026-01-31"}).prepare()
				return err
			},
			want: "from must be a date in YYYY-MM-DD format",
		},
		{
			name: "bad to date",
			prepare: func() error {
				_, err := (priceHistoryInput{Symbol: "AAPL", From: "2026-01-01", To: "nope"}).prepare()
				return err
			},
			want: "to must be a date in YYYY-MM-DD format",
		},
		{
			name: "from after to",
			prepare: func() error {
				_, err := (priceHistoryInput{Symbol: "AAPL", From: "2026-02-01", To: "2026-01-31"}).prepare()
				return err
			},
			want: "from must be on or before to",
		},
		{
			name: "bad interval",
			prepare: func() error {
				_, err := (priceHistoryInput{Symbol: "AAPL", Interval: "hourly"}).prepare()
				return err
			},
			want: "interval must be 'day', 'week', or 'month'",
		},
		{
			name: "bad period",
			prepare: func() error {
				_, err := (financialStatementsInput{Symbol: "AAPL", Statement: "income", Period: "monthly"}).prepare()
				return err
			},
			want: "period must be 'annual' or 'quarter'",
		},
		{
			name: "statement required",
			prepare: func() error {
				_, err := (financialStatementsInput{Symbol: "AAPL", Statement: "  "}).prepare()
				return err
			},
			want: "statement must be 'income', 'balance', or 'cashflow'",
		},
		{
			name: "bad statement",
			prepare: func() error {
				_, err := (financialStatementsInput{Symbol: "AAPL", Statement: "invalid"}).prepare()
				return err
			},
			want: "statement must be 'income', 'balance', or 'cashflow'",
		},
		{
			name: "unknown fundamentals section",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "AAPL", Sections: []string{"profile", "invalid"}}).prepare()
				return err
			},
			want: "unknown section \"invalid\": valid sections are 'profile', 'key_metrics', 'ratios'",
		},
		{
			name: "bad option type",
			prepare: func() error {
				_, err := (optionsChainInput{Symbol: "AAPL", Expiry: "2026-01-16", OptionType: "straddle"}).prepare()
				return err
			},
			want: "option_type must be 'call' or 'put'",
		},
		{
			name: "missing expiry",
			prepare: func() error {
				_, err := (optionsChainInput{Symbol: "AAPL", Expiry: ""}).prepare()
				return err
			},
			want: "expiry is required; use get_option_expirations to list available dates",
		},
		{
			name: "blank expiry",
			prepare: func() error {
				_, err := (optionsChainInput{Symbol: "AAPL", Expiry: "   "}).prepare()
				return err
			},
			want: "expiry is required; use get_option_expirations to list available dates",
		},
		{
			name: "bad expiry",
			prepare: func() error {
				_, err := (optionsChainInput{Symbol: "AAPL", Expiry: "2026/01/16"}).prepare()
				return err
			},
			want: "expiry must be a date in YYYY-MM-DD format",
		},
		{
			name: "strike min after max",
			prepare: func() error {
				min, max := 200.0, 100.0
				_, err := (optionsChainInput{Symbol: "AAPL", Expiry: "2026-01-16", StrikeMin: &min, StrikeMax: &max}).prepare()
				return err
			},
			want: "strike_min must be on or before strike_max",
		},
		{
			name: "empty query",
			prepare: func() error {
				_, err := (resolveSymbolInput{Query: "   "}).prepare()
				return err
			},
			want: "query must be between 1 and 100 characters",
		},
		{
			name: "query too long",
			prepare: func() error {
				_, err := (resolveSymbolInput{Query: strings.Repeat("a", maxQueryLength+1)}).prepare()
				return err
			},
			want: "query must be between 1 and 100 characters",
		},
		{
			name: "bad exchange on resolve symbol",
			prepare: func() error {
				_, err := (resolveSymbolInput{
					Query:    "apple",
					Exchange: "XETRA",
				}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
		{
			name: "bad exchange on price history",
			prepare: func() error {
				_, err := (priceHistoryInput{
					Symbol:   "AAPL",
					From:     "2026-01-01",
					To:       "2026-01-31",
					Exchange: "XETRA",
				}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
		{
			name: "bad exchange on fundamentals",
			prepare: func() error {
				_, err := (fundamentalsInput{Symbol: "AAPL", Exchange: "XETRA"}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
		{
			name: "bad exchange on financial statements",
			prepare: func() error {
				_, err := (financialStatementsInput{Symbol: "AAPL", Statement: "income", Exchange: "XETRA"}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
		{
			name: "symbol required on quote",
			prepare: func() error {
				_, err := (quoteInput{Symbol: "   "}).prepare()
				return err
			},
			want: "symbol is required",
		},
		{
			name: "bad exchange on quote",
			prepare: func() error {
				_, err := (quoteInput{Symbol: "AAPL", Exchange: "XETRA"}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
		{
			name: "technical indicator symbol required",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "", Indicator: "rsi"}).prepare()
				return err
			},
			want: "symbol is required",
		},
		{
			name: "technical indicator invalid type",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "invalid"}).prepare()
				return err
			},
			want: "indicator must be 'sma', 'ema', 'rsi', 'macd', or 'bollinger'",
		},
		{
			name: "technical indicator period too small",
			prepare: func() error {
				p := 1
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", Period: &p}).prepare()
				return err
			},
			want: "period must be between 2 and 400",
		},
		{
			name: "technical indicator period too large",
			prepare: func() error {
				p := 401
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", Period: &p}).prepare()
				return err
			},
			want: "period must be between 2 and 400",
		},
		{
			name: "technical indicator fast out of range",
			prepare: func() error {
				f := 1
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "macd", Fast: &f}).prepare()
				return err
			},
			want: "fast must be between 2 and 400",
		},
		{
			name: "technical indicator slow out of range",
			prepare: func() error {
				s := 401
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "macd", Slow: &s}).prepare()
				return err
			},
			want: "slow must be between 2 and 400",
		},
		{
			name: "technical indicator signal out of range",
			prepare: func() error {
				sig := 1
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "macd", Signal: &sig}).prepare()
				return err
			},
			want: "signal must be between 2 and 400",
		},
		{
			name: "technical indicator std_dev non-positive",
			prepare: func() error {
				sd := 0.0
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "bollinger", StdDev: &sd}).prepare()
				return err
			},
			want: "std_dev must be greater than 0",
		},
		{
			name: "technical indicator bad from date",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", From: "not-a-date"}).prepare()
				return err
			},
			want: "from must be a date in YYYY-MM-DD format",
		},
		{
			name: "technical indicator bad to date",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", To: "2026-13-45"}).prepare()
				return err
			},
			want: "to must be a date in YYYY-MM-DD format",
		},
		{
			name: "technical indicator from after to",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", From: "2026-02-01", To: "2026-01-01"}).prepare()
				return err
			},
			want: "from must be on or before to",
		},
		{
			name: "bad exchange on technical indicator",
			prepare: func() error {
				_, err := (technicalIndicatorInput{Symbol: "AAPL", Indicator: "rsi", Exchange: "XETRA"}).prepare()
				return err
			},
			want: "exchange must be one of: NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := tc.prepare()
			if err == nil {
				t.Fatalf("prepare() = nil error, want %q", tc.want)
			}
			if err.Error() != tc.want {
				t.Errorf("error = %q, want %q", err.Error(), tc.want)
			}
			assertNoProviderName(t, "validation error", err.Error())
		})
	}
}

func TestToolsRejectMissingRequiredInputAtSDK(t *testing.T) {
	backend, _ := newStubBackend(t, http.StatusOK, priceHistoryBody)
	session := newTestSession(t, backend.URL)

	// `symbol` is non-omitempty, so the SDK rejects the call before the
	// handler runs when omitted.
	result := callTool(t, session, "get_price_history", map[string]any{})
	if !result.IsError {
		t.Fatalf("expected the SDK to reject a missing required argument, got %q", resultText(t, result))
	}

	// `statement` is non-omitempty on get_financial_statements, so the SDK rejects
	// the call before the handler runs when omitted.
	resultStmt := callTool(t, session, "get_financial_statements", map[string]any{"symbol": "AAPL"})
	if !resultStmt.IsError {
		t.Fatalf("expected the SDK to reject missing statement argument, got %q", resultText(t, resultStmt))
	}

	// `expiry` is non-omitempty on get_options_chain, so the SDK rejects
	// the call before the handler runs when omitted.
	resultChain := callTool(t, session, "get_options_chain", map[string]any{"symbol": "AAPL"})
	if !resultChain.IsError {
		t.Fatalf("expected the SDK to reject missing expiry argument, got %q", resultText(t, resultChain))
	}
}

func TestToolsRejectBeforeBackendCall(t *testing.T) {
	backend, captured := newStubBackend(t, http.StatusOK, `{"detail":"should not be reached"}`)
	session := newTestSession(t, backend.URL)

	t.Run("unknown section rejected before backend call", func(t *testing.T) {
		captured.path = ""
		res := callTool(t, session, "get_fundamentals", map[string]any{
			"symbol":   "AAPL",
			"sections": []string{"invalid_sec"},
		})
		if !res.IsError {
			t.Fatalf("expected error result, got %q", resultText(t, res))
		}
		text := resultText(t, res)
		if !strings.Contains(text, "profile") || !strings.Contains(text, "key_metrics") || !strings.Contains(text, "ratios") {
			t.Errorf("expected error listing valid names, got %q", text)
		}
		if captured.path != "" {
			t.Errorf("backend called unexpectedly: %s", captured.path)
		}
	})

	t.Run("invalid statement rejected before backend call", func(t *testing.T) {
		captured.path = ""
		res := callTool(t, session, "get_financial_statements", map[string]any{
			"symbol":    "AAPL",
			"statement": "invalid_stmt",
		})
		if !res.IsError {
			t.Fatalf("expected error result, got %q", resultText(t, res))
		}
		text := resultText(t, res)
		if !strings.Contains(text, "income") || !strings.Contains(text, "balance") || !strings.Contains(text, "cashflow") {
			t.Errorf("expected error listing valid statements, got %q", text)
		}
		if captured.path != "" {
			t.Errorf("backend called unexpectedly: %s", captured.path)
		}
	})

	t.Run("missing statement rejected before backend call", func(t *testing.T) {
		captured.path = ""
		res := callTool(t, session, "get_financial_statements", map[string]any{
			"symbol": "AAPL",
		})
		if !res.IsError {
			t.Fatalf("expected error result, got %q", resultText(t, res))
		}
		if captured.path != "" {
			t.Errorf("backend called unexpectedly: %s", captured.path)
		}
	})

	t.Run("missing or blank expiry rejected before backend call naming get_option_expirations", func(t *testing.T) {
		captured.path = ""
		res := callTool(t, session, "get_options_chain", map[string]any{
			"symbol": "AAPL",
			"expiry": "   ",
		})
		if !res.IsError {
			t.Fatalf("expected error result, got %q", resultText(t, res))
		}
		text := resultText(t, res)
		if !strings.Contains(text, "get_option_expirations") {
			t.Errorf("expected error naming get_option_expirations, got %q", text)
		}
		if captured.path != "" {
			t.Errorf("backend called unexpectedly: %s", captured.path)
		}
	})

	t.Run("invalid symbols rejected before backend call", func(t *testing.T) {
		invalidSymbols := []string{
			"AAPL/EXPIRATIONS",
			"A%2FB",
			"..",
			"BRK B",
			"AAPL\n",
			"^",
			strings.Repeat("A", 33),
		}
		for _, sym := range invalidSymbols {
			captured.path = ""
			res := callTool(t, session, "get_quote", map[string]any{
				"symbol": sym,
			})
			if !res.IsError {
				t.Fatalf("expected error result for symbol %q, got success", sym)
			}
			if captured.path != "" {
				t.Errorf("backend called unexpectedly for symbol %q: %s", sym, captured.path)
			}
		}
	})
}

func TestRequireSymbol(t *testing.T) {
	accepted := []string{
		"AAPL",
		"aapl",
		"BRK.B",
		"RY.TO",
		"VOD.L",
		"SHOP-A",
		"^GSPC",
		"EURUSD=X",
	}
	for _, sym := range accepted {
		t.Run("accept_"+sym, func(t *testing.T) {
			got, err := requireSymbol(sym)
			if err != nil {
				t.Fatalf("requireSymbol(%q) unexpected error: %v", sym, err)
			}
			if got != sym {
				t.Errorf("requireSymbol(%q) = %q, want %q", sym, got, sym)
			}
		})
	}

	rejected := []struct {
		sym  string
		want string
	}{
		{"AAPL/EXPIRATIONS", `invalid symbol "AAPL/EXPIRATIONS"`},
		{"A%2FB", `invalid symbol "A%2FB"`},
		{"..", `invalid symbol ".."`},
		{"BRK B", `invalid symbol "BRK B"`},
		{"AAPL\n", "invalid symbol \"AAPL\\n\""},
		{"^", `invalid symbol "^"`},
		{strings.Repeat("A", 33), "symbol must be at most 32 characters"},
	}
	for _, tc := range rejected {
		t.Run("reject_"+tc.sym, func(t *testing.T) {
			got, err := requireSymbol(tc.sym)
			if err == nil {
				t.Fatalf("requireSymbol(%q) = %q, expected error", tc.sym, got)
			}
			if err.Error() != tc.want {
				t.Errorf("requireSymbol(%q) error = %q, want %q", tc.sym, err.Error(), tc.want)
			}
			assertNoProviderName(t, "symbol rejection error", err.Error())
		})
	}
}

func newTestSessionWithEnv(t *testing.T, backendURL, env string) *mcp.ClientSession {
	t.Helper()
	client := mustClient(t, backendURL, "test-token", env)
	cfg := Config{Environment: env}
	srv := httptest.NewServer(newRouter(newMCPServer(client, cfg), cfg))
	t.Cleanup(srv.Close)

	mcpClient := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.1"}, nil)
	session, err := mcpClient.Connect(context.Background(), &mcp.StreamableClientTransport{
		Endpoint:             srv.URL + "/mcp",
		DisableStandaloneSSE: true,
	}, nil)
	if err != nil {
		t.Fatalf("connect to /mcp: %v", err)
	}
	t.Cleanup(func() { _ = session.Close() })
	return session
}

func TestTools_DevExecutionLogging(t *testing.T) {
	var buf bytes.Buffer
	logger, err := newLogger(&buf, "dev", "DEBUG")
	if err != nil {
		t.Fatalf("newLogger error: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	backend, _ := newStubBackend(t, http.StatusOK, `{"symbol":"AAPL","prices":[{"date":"2024-01-01","open":"10","high":"12","low":"9","close":"11","volume":100}]}`)
	session := newTestSessionWithEnv(t, backend.URL, "dev")

	res := callTool(t, session, "get_price_history", map[string]any{
		"symbol": "AAPL",
		"from":   "2024-01-01",
		"to":     "2024-01-02",
	})
	if res.IsError {
		t.Fatalf("callTool returned error: %+v", res)
	}

	out := buf.String()
	if !strings.Contains(out, "DEBUG") {
		t.Errorf("expected DEBUG logs in dev mode, got:\n%s", out)
	}
	if !strings.Contains(out, "tool=get_price_history") {
		t.Errorf("expected tool name in logs, got:\n%s", out)
	}
	if !strings.Contains(out, "arguments=") || !strings.Contains(out, "AAPL") {
		t.Errorf("expected arguments in logs, got:\n%s", out)
	}
	if !strings.Contains(out, "duration=") {
		t.Errorf("expected duration in logs, got:\n%s", out)
	}
	if !strings.Contains(out, "response=") || !strings.Contains(out, "2024-01-01") {
		t.Errorf("expected response payload content in logs, got:\n%s", out)
	}
}

func TestTools_ErrorLogging(t *testing.T) {
	t.Run("input validation error", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		backend, _ := newStubBackend(t, http.StatusOK, `{}`)
		session := newTestSessionWithEnv(t, backend.URL, "prod")

		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol": "AAPL",
			"from":   "2024-01-05",
			"to":     "2024-01-01", // from > to
		})
		if !res.IsError {
			t.Fatal("expected error for invalid dates")
		}

		out := buf.String()
		if !strings.Contains(out, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log, got:\n%s", out)
		}
		if !strings.Contains(out, `"tool":"get_price_history"`) {
			t.Errorf("expected tool name in log, got:\n%s", out)
		}
		if !strings.Contains(out, `"arguments":`) {
			t.Errorf("expected arguments in log, got:\n%s", out)
		}
		if !strings.Contains(out, `"error_class":"ErrValidation"`) {
			t.Errorf("expected error_class ErrValidation, got:\n%s", out)
		}
		if !strings.Contains(out, `"status":400`) {
			t.Errorf("expected status 400, got:\n%s", out)
		}
		if !strings.Contains(out, `"detail":`) {
			t.Errorf("expected detail in log, got:\n%s", out)
		}
	})

	t.Run("422 backend validation error", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		backend, _ := newStubBackend(t, http.StatusUnprocessableEntity, `{"detail":"from must be before to"}`)
		session := newTestSessionWithEnv(t, backend.URL, "prod")

		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol": "AAPL",
			"from":   "2024-01-01",
			"to":     "2024-01-02",
		})
		if !res.IsError {
			t.Fatal("expected error on 422")
		}

		out := buf.String()
		if !strings.Contains(out, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log, got:\n%s", out)
		}
		if !strings.Contains(out, `"tool":"get_price_history"`) {
			t.Errorf("expected tool name in log, got:\n%s", out)
		}
		if !strings.Contains(out, `"error_class":"ErrValidation"`) {
			t.Errorf("expected error_class ErrValidation, got:\n%s", out)
		}
		if !strings.Contains(out, `"status":422`) {
			t.Errorf("expected status 422, got:\n%s", out)
		}
		if !strings.Contains(out, `"detail":`) {
			t.Errorf("expected detail in log, got:\n%s", out)
		}
	})

	t.Run("401 configuration error", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		backend, _ := newStubBackend(t, http.StatusUnauthorized, `{"detail":"bad token"}`)
		session := newTestSessionWithEnv(t, backend.URL, "prod")

		res := callTool(t, session, "get_fundamentals", map[string]any{
			"symbol": "AAPL",
		})
		if !res.IsError {
			t.Fatal("expected error on 401")
		}

		out := buf.String()
		if !strings.Contains(out, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log, got:\n%s", out)
		}
		if !strings.Contains(out, `"tool":"get_fundamentals"`) {
			t.Errorf("expected tool name in log, got:\n%s", out)
		}
		if !strings.Contains(out, `"error_class":"ErrConfiguration"`) {
			t.Errorf("expected error_class ErrConfiguration, got:\n%s", out)
		}
		if !strings.Contains(out, `"status":401`) {
			t.Errorf("expected status 401, got:\n%s", out)
		}
	})

	t.Run("500 provider error", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		backend, _ := newStubBackend(t, http.StatusInternalServerError, `{"detail":"provider down"}`)
		session := newTestSessionWithEnv(t, backend.URL, "prod")

		res := callTool(t, session, "get_fundamentals", map[string]any{
			"symbol": "AAPL",
		})
		if !res.IsError {
			t.Fatal("expected error on 500")
		}

		out := buf.String()
		if !strings.Contains(out, `"level":"ERROR"`) {
			t.Errorf("expected ERROR level log, got:\n%s", out)
		}
		if !strings.Contains(out, `"tool":"get_fundamentals"`) {
			t.Errorf("expected tool name in log, got:\n%s", out)
		}
		if !strings.Contains(out, `"error_class":"ErrProvider"`) {
			t.Errorf("expected error_class ErrProvider, got:\n%s", out)
		}
		if !strings.Contains(out, `"status":500`) {
			t.Errorf("expected status 500, got:\n%s", out)
		}
	})

	t.Run("ErrNoData 404 does not emit ERROR log and logs completion in dev", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "dev", "DEBUG")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		backend, _ := newStubBackend(t, http.StatusNotFound, `{"detail":"not found"}`)
		session := newTestSessionWithEnv(t, backend.URL, "dev")

		res := callTool(t, session, "get_fundamentals", map[string]any{
			"symbol": "AAPL",
		})
		if res.IsError {
			t.Fatal("ErrNoData should not be an error in tool result")
		}

		out := buf.String()
		// Verify no ERROR logs were emitted for tool execution failed
		for _, line := range strings.Split(out, "\n") {
			if strings.Contains(line, "tool execution failed") {
				t.Fatalf("ErrNoData should not emit 'tool execution failed' log: %s", line)
			}
		}

		// Verify dev completion log was emitted
		if !strings.Contains(out, "tool execution completed") {
			t.Errorf("expected 'tool execution completed' in dev log, got:\n%s", out)
		}
		if !strings.Contains(out, noDataMessage) {
			t.Errorf("expected noDataMessage in dev log, got:\n%s", out)
		}
	})
}

func TestTools_ProviderNameCompliance(t *testing.T) {
	var buf bytes.Buffer
	logger, err := newLogger(&buf, "dev", "DEBUG")
	if err != nil {
		t.Fatalf("newLogger error: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	backend, _ := newStubBackend(t, http.StatusOK, `{"symbol":"AAPL","prices":[]}`)
	session := newTestSessionWithEnv(t, backend.URL, "dev")

	callTool(t, session, "get_price_history", map[string]any{
		"symbol": "AAPL",
		"from":   "2024-01-01",
		"to":     "2024-01-02",
	})

	assertNoProviderName(t, "tool execution log", buf.String())

	// Assert no tool names, titles, descriptions, or schema texts mention upstream provider brands.
	toolsResult, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatalf("ListTools: %v", err)
	}
	for _, tool := range toolsResult.Tools {
		assertNoProviderName(t, "tool name: "+tool.Name, tool.Name)
		assertNoProviderName(t, "tool description: "+tool.Name, tool.Description)
		if tool.Annotations != nil {
			assertNoProviderName(t, "tool title: "+tool.Name, tool.Annotations.Title)
		}
		schemaBytes, err := json.Marshal(tool.InputSchema)
		if err != nil {
			t.Fatalf("marshal input schema for %s: %v", tool.Name, err)
		}
		assertNoProviderName(t, "tool schema: "+tool.Name, string(schemaBytes))
	}
}

func TestToolSurfaceContract(t *testing.T) {
	session := newTestSession(t, "http://backend.invalid")
	toolsResult, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatalf("ListTools failed: %v", err)
	}

	expectedTools := []string{
		"resolve_symbol",
		"get_quote",
		"get_price_history",
		"get_fundamentals",
		"get_financial_statements",
		"get_option_expirations",
		"get_options_chain",
		"get_technical_indicator",
	}

	registeredNames := make(map[string]bool, len(expectedTools))
	for _, name := range expectedTools {
		registeredNames[name] = true
	}

	gotTools := make(map[string]*mcp.Tool, len(toolsResult.Tools))
	for _, tool := range toolsResult.Tools {
		gotTools[tool.Name] = tool
	}

	if len(gotTools) != len(expectedTools) {
		t.Fatalf("got %d tools, want %d", len(gotTools), len(expectedTools))
	}
	for _, name := range expectedTools {
		if _, ok := gotTools[name]; !ok {
			t.Errorf("expected tool %q not found in ListTools", name)
		}
	}

	requiredSections := []string{"Use when:", "Examples:", "Returns:", "See also:"}

	for _, tool := range toolsResult.Tools {
		t.Run(tool.Name, func(t *testing.T) {
			if tool.Annotations == nil {
				t.Fatalf("%s: missing annotations", tool.Name)
			}
			if !tool.Annotations.ReadOnlyHint {
				t.Errorf("%s: readOnlyHint = false, want true", tool.Name)
			}
			if tool.Annotations.Title == "" {
				t.Errorf("%s: annotations.title is empty", tool.Name)
			}

			desc := tool.Description
			if desc == "" {
				t.Fatalf("%s: description is empty", tool.Name)
			}

			for _, sec := range requiredSections {
				if !strings.Contains(desc, sec) {
					t.Errorf("%s: description missing section %q", tool.Name, sec)
				}
			}

			// Verify at least two example lines under Examples:
			examplesIdx := strings.Index(desc, "Examples:")
			returnsIdx := strings.Index(desc, "Returns:")
			if examplesIdx != -1 && returnsIdx != -1 && returnsIdx > examplesIdx {
				examplesBlock := desc[examplesIdx+len("Examples:") : returnsIdx]
				lines := strings.Split(examplesBlock, "\n")
				exampleCount := 0
				for _, line := range lines {
					trimmed := strings.TrimSpace(line)
					if strings.HasPrefix(trimmed, "-") && strings.Contains(trimmed, "->") {
						exampleCount++
					}
				}
				if exampleCount < 2 {
					t.Errorf("%s: found %d example lines, want at least 2", tool.Name, exampleCount)
				}
			} else {
				t.Errorf("%s: malformed Examples/Returns structure", tool.Name)
			}

			// Verify See also: targets name only registered tools
			seeAlsoIdx := strings.Index(desc, "See also:")
			if seeAlsoIdx != -1 {
				seeAlsoBlock := desc[seeAlsoIdx+len("See also:"):]
				tokens := strings.FieldsFunc(seeAlsoBlock, func(r rune) bool {
					return r == ',' || r == '\n' || r == '\r' || r == ' ' || r == '\t'
				})
				var targets []string
				for _, tok := range tokens {
					tok = strings.Trim(tok, "`\"'.,")
					if tok != "" {
						targets = append(targets, tok)
					}
				}
				if len(targets) == 0 {
					t.Errorf("%s: See also has no targets", tool.Name)
				}
				for _, target := range targets {
					if !registeredNames[target] {
						t.Errorf("%s: See also references unregistered tool %q", tool.Name, target)
					}
				}
			}
		})
	}

	// resolve_symbol's description says to use it first
	resolveSymbolDesc := gotTools["resolve_symbol"].Description
	if !strings.Contains(strings.ToLower(resolveSymbolDesc), "use this first") {
		t.Errorf("resolve_symbol description should say to use it first, got: %s", resolveSymbolDesc)
	}

	// get_options_chain's explains truncated and how to narrow (strike range, option type)
	optionsChainDesc := gotTools["get_options_chain"].Description
	if !strings.Contains(optionsChainDesc, "truncated") {
		t.Errorf("get_options_chain description must explain 'truncated'")
	}
	if !strings.Contains(optionsChainDesc, "strike") || !strings.Contains(optionsChainDesc, "option_type") {
		t.Errorf("get_options_chain description must explain how to narrow (strike range, option type)")
	}

	// get_price_history's states the 2,000-bar cap and suggests intervals
	priceHistoryDesc := gotTools["get_price_history"].Description
	if !strings.Contains(priceHistoryDesc, "2,000") && !strings.Contains(priceHistoryDesc, "2000") {
		t.Errorf("get_price_history description must state 2,000-bar cap")
	}
	if !strings.Contains(priceHistoryDesc, "interval") {
		t.Errorf("get_price_history description must suggest intervals")
	}

	// get_quote's mentions the timestamp
	quoteDesc := gotTools["get_quote"].Description
	if !strings.Contains(quoteDesc, "timestamp") {
		t.Errorf("get_quote description must mention timestamp")
	}
}

func TestExchangeNormalizationInPrepare(t *testing.T) {
	t.Run("priceHistoryInput normalizes lowercase", func(t *testing.T) {
		req, err := (priceHistoryInput{
			Symbol:   "AAPL",
			From:     "2026-01-01",
			To:       "2026-01-31",
			Exchange: "tsx",
		}).prepare()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if req.exchange != "TSX" {
			t.Errorf("req.exchange = %q, want %q", req.exchange, "TSX")
		}
	})

	t.Run("fundamentalsInput normalizes lowercase", func(t *testing.T) {
		req, err := (fundamentalsInput{Symbol: "AAPL", Exchange: "tsx"}).prepare()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if req.exchange != "TSX" {
			t.Errorf("req.exchange = %q, want %q", req.exchange, "TSX")
		}
	})

	t.Run("financialStatementsInput normalizes lowercase", func(t *testing.T) {
		req, err := (financialStatementsInput{Symbol: "AAPL", Statement: "income", Exchange: "tsx"}).prepare()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if req.exchange != "TSX" {
			t.Errorf("req.exchange = %q, want %q", req.exchange, "TSX")
		}
	})

	t.Run("resolveSymbolInput normalizes lowercase", func(t *testing.T) {
		req, err := (resolveSymbolInput{Query: "AAPL", Exchange: "tsx"}).prepare()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if req.exchange != "TSX" {
			t.Errorf("req.exchange = %q, want %q", req.exchange, "TSX")
		}
	})

	t.Run("technicalIndicatorInput normalizes lowercase", func(t *testing.T) {
		req, err := (technicalIndicatorInput{
			Symbol:    "AAPL",
			Indicator: "rsi",
			Exchange:  "tsx",
		}).prepare()
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if req.query.exchange != "TSX" {
			t.Errorf("req.query.exchange = %q, want %q", req.query.exchange, "TSX")
		}
	})
}

func TestToolsExchangeValidationAndWireValue(t *testing.T) {
	toolsWithExchange := []struct {
		name string
		args func(exchange string) map[string]any
	}{
		{"get_price_history", func(ex string) map[string]any {
			return map[string]any{"symbol": "AAPL", "from": "2024-01-01", "to": "2024-01-02", "exchange": ex}
		}},
		{"get_fundamentals", func(ex string) map[string]any {
			return map[string]any{"symbol": "AAPL", "exchange": ex}
		}},
		{"get_financial_statements", func(ex string) map[string]any {
			return map[string]any{"symbol": "AAPL", "statement": "income", "exchange": ex}
		}},
		{"get_technical_indicator", func(ex string) map[string]any {
			return map[string]any{"symbol": "AAPL", "indicator": "rsi", "exchange": ex}
		}},
	}

	for _, tt := range toolsWithExchange {
		t.Run(tt.name+"_rejects_invalid_exchange", func(t *testing.T) {
			backendCalls := 0
			backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				backendCalls++
				w.WriteHeader(http.StatusOK)
			}))
			defer backend.Close()

			session := newTestSession(t, backend.URL)
			res := callTool(t, session, tt.name, tt.args("XETRA"))
			if !res.IsError {
				t.Fatalf("expected tool %s to fail with exchange=XETRA", tt.name)
			}
			if backendCalls != 0 {
				t.Errorf("expected 0 backend calls, got %d", backendCalls)
			}
			msg := resultText(t, res)
			for _, code := range supportedExchanges {
				if !strings.Contains(msg, code) {
					t.Errorf("expected error message to contain accepted code %q, got: %s", code, msg)
				}
			}
		})

		t.Run(tt.name+"_accepts_lowercase_exchange_and_sends_uppercase", func(t *testing.T) {
			var recordedExchange string
			backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				recordedExchange = r.URL.Query().Get("exchange")
				w.Header().Set("Content-Type", "application/json")
				switch {
				case strings.Contains(r.URL.Path, "/prices/"):
					_, _ = w.Write([]byte(`{"symbol":"AAPL","exchange":"TSX","from_date":"2024-01-01","to_date":"2024-01-02","items":[]}`))
				case strings.HasSuffix(r.URL.Path, "/statements"):
					_, _ = w.Write([]byte(`[]`))
				case strings.Contains(r.URL.Path, "/fundamentals/"):
					_, _ = w.Write([]byte(`{"profile":{"symbol":"AAPL","company_name":"Apple Inc."}}`))
				default:
					_, _ = w.Write([]byte(`{}`))
				}
			}))
			defer backend.Close()

			session := newTestSession(t, backend.URL)
			res := callTool(t, session, tt.name, tt.args("tsx"))
			if res.IsError {
				t.Fatalf("expected tool %s to succeed with exchange=tsx, got error: %s", tt.name, resultText(t, res))
			}
			if recordedExchange != "TSX" {
				t.Errorf("tool %s sent exchange query param %q, want %q", tt.name, recordedExchange, "TSX")
			}
		})
	}
}
