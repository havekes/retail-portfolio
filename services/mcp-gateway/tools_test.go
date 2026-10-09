package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
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

func TestFundamentalsSectionSelectionAndNullHandling(t *testing.T) {
	const (
		nullRatiosBody = `{
			"profile": {"symbol": "AAPL", "company_name": "Apple Inc."},
			"key_metrics": {"symbol": "AAPL", "date": "2024-09-28", "pe_ratio": "36.28"},
			"ratios": null
		}`
		nullKeyMetricsBody = `{
			"profile": {"symbol": "AAPL", "company_name": "Apple Inc."},
			"key_metrics": null,
			"ratios": {"symbol": "AAPL", "date": "2024-09-28", "debt_to_equity": "1.87"}
		}`
		nullBothBody = `{
			"profile": {"symbol": "AAPL", "company_name": "Apple Inc."},
			"key_metrics": null,
			"ratios": null
		}`
		absentRatiosBody = `{
			"profile": {"symbol": "AAPL", "company_name": "Apple Inc."},
			"key_metrics": {"symbol": "AAPL", "date": "2024-09-28", "pe_ratio": "36.28"}
		}`
		allNullBody = `{
			"profile": null,
			"key_metrics": null,
			"ratios": null
		}`
	)

	tests := []struct {
		name       string
		args       map[string]any
		body       string
		wantNoData bool
		assertData func(t *testing.T, raw string)
	}{
		{
			name:       "null ratios: sections=['ratios'] returns no-data",
			args:       map[string]any{"symbol": "AAPL", "sections": []string{"ratios"}},
			body:       nullRatiosBody,
			wantNoData: true,
		},
		{
			name: "null ratios: sections=['profile', 'ratios'] returns profile and null ratios",
			args: map[string]any{"symbol": "AAPL", "sections": []string{"profile", "ratios"}},
			body: nullRatiosBody,
			assertData: func(t *testing.T, raw string) {
				var got map[string]json.RawMessage
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode fundamentals: %v", err)
				}
				if len(got) != 2 {
					t.Errorf("len(got) = %d, want 2: %+v", len(got), got)
				}
				if string(got["ratios"]) != "null" {
					t.Errorf("ratios = %s, want null", got["ratios"])
				}
				if _, ok := got["profile"]; !ok {
					t.Errorf("missing profile key: %+v", got)
				}
				if _, ok := got["key_metrics"]; ok {
					t.Errorf("unexpected key_metrics key: %+v", got)
				}
			},
		},
		{
			name: "null ratios: omitted sections returns all 3 with null ratios",
			args: map[string]any{"symbol": "AAPL"},
			body: nullRatiosBody,
			assertData: func(t *testing.T, raw string) {
				var got map[string]json.RawMessage
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode fundamentals: %v", err)
				}
				if len(got) != 3 {
					t.Errorf("len(got) = %d, want 3: %+v", len(got), got)
				}
				if string(got["ratios"]) != "null" {
					t.Errorf("ratios = %s, want null", got["ratios"])
				}
			},
		},
		{
			name:       "absent ratios: sections=['ratios'] returns no-data",
			args:       map[string]any{"symbol": "AAPL", "sections": []string{"ratios"}},
			body:       absentRatiosBody,
			wantNoData: true,
		},
		{
			name:       "null key_metrics: sections=['key_metrics'] returns no-data",
			args:       map[string]any{"symbol": "AAPL", "sections": []string{"key_metrics"}},
			body:       nullKeyMetricsBody,
			wantNoData: true,
		},
		{
			name: "null key_metrics: sections=['profile', 'key_metrics'] returns profile and null key_metrics",
			args: map[string]any{"symbol": "AAPL", "sections": []string{"profile", "key_metrics"}},
			body: nullKeyMetricsBody,
			assertData: func(t *testing.T, raw string) {
				var got map[string]json.RawMessage
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode fundamentals: %v", err)
				}
				if len(got) != 2 {
					t.Errorf("len(got) = %d, want 2: %+v", len(got), got)
				}
				if string(got["key_metrics"]) != "null" {
					t.Errorf("key_metrics = %s, want null", got["key_metrics"])
				}
			},
		},
		{
			name:       "both null: sections=['key_metrics', 'ratios'] returns no-data",
			args:       map[string]any{"symbol": "AAPL", "sections": []string{"key_metrics", "ratios"}},
			body:       nullBothBody,
			wantNoData: true,
		},
		{
			name: "both null: omitted sections returns profile and null for both",
			args: map[string]any{"symbol": "AAPL"},
			body: nullBothBody,
			assertData: func(t *testing.T, raw string) {
				var got map[string]json.RawMessage
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode fundamentals: %v", err)
				}
				if string(got["key_metrics"]) != "null" || string(got["ratios"]) != "null" {
					t.Errorf("expected both null: %+v", got)
				}
			},
		},
		{
			name:       "all null: omitted sections returns no-data",
			args:       map[string]any{"symbol": "AAPL"},
			body:       allNullBody,
			wantNoData: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			backend, _ := newStubBackend(t, http.StatusOK, tc.body)
			session := newTestSession(t, backend.URL)

			result := callTool(t, session, "get_fundamentals", tc.args)
			if result.IsError {
				t.Fatalf("callTool(get_fundamentals) failed: %s", resultText(t, result))
			}
			raw := resultText(t, result)
			assertNoProviderName(t, "tool result", raw)

			if tc.wantNoData {
				if raw != noDataMessage {
					t.Errorf("expected noDataMessage %q, got %q", noDataMessage, raw)
				}
			} else {
				tc.assertData(t, raw)
			}
		})
	}
}

func TestFundamentalsSectionSelectionOnlyRequestedKeys(t *testing.T) {
	backend, _ := newStubBackend(t, http.StatusOK, fundamentalsBody)
	session := newTestSession(t, backend.URL)

	cases := []struct {
		name     string
		args     map[string]any
		wantKeys []string
	}{
		{
			name:     "only ratios requested",
			args:     map[string]any{"symbol": "AAPL", "sections": []string{"ratios"}},
			wantKeys: []string{"ratios"},
		},
		{
			name:     "only profile requested",
			args:     map[string]any{"symbol": "AAPL", "sections": []string{"profile"}},
			wantKeys: []string{"profile"},
		},
		{
			name:     "only key_metrics requested",
			args:     map[string]any{"symbol": "AAPL", "sections": []string{"key_metrics"}},
			wantKeys: []string{"key_metrics"},
		},
		{
			name:     "profile and key_metrics requested",
			args:     map[string]any{"symbol": "AAPL", "sections": []string{"profile", "key_metrics"}},
			wantKeys: []string{"profile", "key_metrics"},
		},
		{
			name:     "deduped sections",
			args:     map[string]any{"symbol": "AAPL", "sections": []string{"ratios", "ratios"}},
			wantKeys: []string{"ratios"},
		},
		{
			name:     "omitted sections returns all three",
			args:     map[string]any{"symbol": "AAPL"},
			wantKeys: []string{"profile", "key_metrics", "ratios"},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			result := callTool(t, session, "get_fundamentals", tc.args)
			if result.IsError {
				t.Fatalf("callTool failed: %s", resultText(t, result))
			}
			var got map[string]json.RawMessage
			if err := json.Unmarshal([]byte(resultText(t, result)), &got); err != nil {
				t.Fatalf("decode: %v", err)
			}
			if len(got) != len(tc.wantKeys) {
				t.Errorf("got %d keys, want %d: %+v", len(got), len(tc.wantKeys), got)
			}
			for _, key := range tc.wantKeys {
				if _, ok := got[key]; !ok {
					t.Errorf("expected key %q missing from: %+v", key, got)
				}
			}
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

func TestStatementToolDecodeFailureIsProviderError(t *testing.T) {
	// A payload missing required header fields served on the statement path
	// cannot be decoded: it is surfaced as a generic tool error, never "no data".
	cases := []struct {
		name string
		body string
	}{
		{"missing date and symbol", `[{"revenue":"1"}]`},
		{"null date", `[{"date": null, "symbol": "AAPL"}]`},
		{"empty date", `[{"date": "", "symbol": "AAPL"}]`},
		{"whitespace date", `[{"date": "   ", "symbol": "AAPL"}]`},
		{"missing symbol", `[{"date": "2024-09-28"}]`},
		{"null symbol", `[{"date": "2024-09-28", "symbol": null}]`},
		{"empty symbol", `[{"date": "2024-09-28", "symbol": ""}]`},
	}

	statementTypes := []string{
		"income",
		"balance",
		"cashflow",
	}

	for _, tc := range cases {
		for _, stmt := range statementTypes {
			t.Run(fmt.Sprintf("%s/%s", stmt, tc.name), func(t *testing.T) {
				backend, _ := newStubBackend(t, http.StatusOK, tc.body)
				session := newTestSession(t, backend.URL)

				result := callTool(t, session, "get_financial_statements", map[string]any{"symbol": "AAPL", "statement": stmt})
				if !result.IsError {
					t.Fatalf("expected an error result, got %q", resultText(t, result))
				}
				if got := resultText(t, result); got != "tool call failed" {
					t.Errorf("result text = %q, want %q", got, "tool call failed")
				}
			})
		}
	}
}

func TestFinancialStatementsPreservesExtraFields(t *testing.T) {
	// A backend statement item carrying an extra field appears unchanged in
	// items. Numbers (including Decimal strings like "123.4500") pass through byte-for-byte.
	const body = `[{
		"date": "2024-09-28",
		"symbol": "AAPL",
		"revenue": "391035000000",
		"new_line_item": "1",
		"decimal_str": "123.4500",
		"int_val": 42
	}]`
	statementTypes := []string{
		"income",
		"balance",
		"cashflow",
	}

	for _, stmt := range statementTypes {
		t.Run(stmt, func(t *testing.T) {
			backend, _ := newStubBackend(t, http.StatusOK, body)
			session := newTestSession(t, backend.URL)

			result := callTool(t, session, "get_financial_statements", map[string]any{"symbol": "AAPL", "statement": stmt})
			if result.IsError {
				t.Fatalf("unexpected error: %s", resultText(t, result))
			}

			var envelope struct {
				Statement string                       `json:"statement"`
				Symbol    string                       `json:"symbol"`
				Items     []map[string]json.RawMessage `json:"items"`
			}
			if err := json.Unmarshal([]byte(resultText(t, result)), &envelope); err != nil {
				t.Fatalf("decode envelope: %v", err)
			}
			if len(envelope.Items) != 1 {
				t.Fatalf("items len = %d, want 1", len(envelope.Items))
			}
			item := envelope.Items[0]
			if string(item["new_line_item"]) != `"1"` {
				t.Errorf("new_line_item = %s, want %q", item["new_line_item"], `"1"`)
			}
			if string(item["decimal_str"]) != `"123.4500"` {
				t.Errorf("decimal_str = %s, want %q", item["decimal_str"], `"123.4500"`)
			}
			if string(item["int_val"]) != "42" {
				t.Errorf("int_val = %s, want 42", item["int_val"])
			}
			if string(item["date"]) != `"2024-09-28"` || string(item["symbol"]) != `"AAPL"` {
				t.Errorf("header fields corrupted: date=%s, symbol=%s", item["date"], item["symbol"])
			}
		})
	}
}

func TestFundamentalsPreservesExtraFields(t *testing.T) {
	// A fundamentals payload with an extra field in profile, key_metrics or
	// ratios appears unchanged in get_fundamentals output.
	const body = `{
		"profile": {
			"symbol": "AAPL",
			"company_name": "Apple Inc.",
			"extra_profile_field": "custom_profile",
			"decimal_str": "123.4500"
		},
		"key_metrics": {
			"symbol": "AAPL",
			"date": "2024-09-28",
			"extra_metric_field": "custom_metric",
			"decimal_str": "123.4500"
		},
		"ratios": {
			"symbol": "AAPL",
			"date": "2024-09-28",
			"extra_ratio_field": "custom_ratio",
			"decimal_str": "123.4500"
		}
	}`

	tests := []struct {
		name     string
		section  string
		extraKey string
		extraVal string
	}{
		{"profile section", "profile", "extra_profile_field", `"custom_profile"`},
		{"key_metrics section", "key_metrics", "extra_metric_field", `"custom_metric"`},
		{"ratios section", "ratios", "extra_ratio_field", `"custom_ratio"`},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			backend, _ := newStubBackend(t, http.StatusOK, body)
			session := newTestSession(t, backend.URL)

			result := callTool(t, session, "get_fundamentals", map[string]any{
				"symbol":   "AAPL",
				"sections": []string{tt.section},
			})
			if result.IsError {
				t.Fatalf("unexpected error: %s", resultText(t, result))
			}

			var aggregate map[string]json.RawMessage
			if err := json.Unmarshal([]byte(resultText(t, result)), &aggregate); err != nil {
				t.Fatalf("decode aggregate: %v", err)
			}
			var section map[string]json.RawMessage
			if err := json.Unmarshal(aggregate[tt.section], &section); err != nil {
				t.Fatalf("decode section %s: %v", tt.section, err)
			}
			if string(section[tt.extraKey]) != tt.extraVal {
				t.Errorf("%s = %s, want %s", tt.extraKey, section[tt.extraKey], tt.extraVal)
			}
			if string(section["decimal_str"]) != `"123.4500"` {
				t.Errorf("decimal_str = %s, want %q", section["decimal_str"], `"123.4500"`)
			}
		})
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

func TestStatementLimitClampAndPeriodDefault(t *testing.T) {
	for _, tc := range []struct {
		in   financialStatementsInput
		want int
		per  string
	}{
		{financialStatementsInput{Symbol: "AAPL", Statement: "income", Limit: 0}, 5, "annual"},
		{financialStatementsInput{Symbol: "AAPL", Statement: "income", Limit: -3}, 5, "annual"},
		{financialStatementsInput{Symbol: "AAPL", Statement: "income", Limit: 25}, 20, "annual"},
		{financialStatementsInput{Symbol: "AAPL", Statement: "income", Limit: 3}, 3, "annual"},
		{financialStatementsInput{Symbol: "AAPL", Statement: "income", Period: "quarter"}, 5, "quarter"},
	} {
		got, err := tc.in.prepare()
		if err != nil {
			t.Fatalf("prepare(%+v): %v", tc.in, err)
		}
		if got.limit != tc.want || got.period != tc.per {
			t.Errorf("prepare(%+v) = limit %d period %q, want limit %d period %q", tc.in, got.limit, got.period, tc.want, tc.per)
		}
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

// Full statement fixtures: every key equals exactly the corresponding Go
// struct's JSON field set (T09 carry-over).
const (
	incomeStatementFixture = `[{
		"date": "2024-09-28", "symbol": "AAPL", "reported_currency": "USD", "cik": "0000320193",
		"filing_date": "2024-11-01", "accepted_date": "2024-11-01T06:01:27.000Z",
		"fiscal_year": "2024", "period": "FY",
		"revenue": "391035000000", "cost_of_revenue": "210352000000", "gross_profit": "180683000000",
		"research_and_development_expenses": "31370000000",
		"selling_general_and_administrative_expenses": "26097000000",
		"operating_expenses": "57447000000", "operating_income": "123216000000",
		"interest_expense": "0", "other_income_expense": "0", "income_tax_expense": "29749000000",
		"net_income": "93736000000", "eps": "6.11", "eps_diluted": "6.08",
		"weighted_average_shares_outstanding": "15343783000",
		"weighted_average_shares_outstanding_diluted": "15408095000"
	}]`

	balanceSheetFixture = `[{
		"date": "2024-09-28", "symbol": "AAPL", "reported_currency": "USD", "cik": "0000320193",
		"fiscal_year": "2024", "period": "FY",
		"total_assets": "364980000000", "current_assets": "152987000000",
		"total_liabilities": "308030000000", "current_liabilities": "176392000000",
		"total_debt": "106629000000", "cash_and_cash_equivalents": "29943000000",
		"inventory": "7286000000", "receivables": "33410000000", "payables": "68960000000",
		"goodwill": "0", "retained_earnings": "-19154000000", "total_equity": "56950000000",
		"common_stock": "83276000000", "net_debt": "76706000000"
	}]`

	cashFlowStatementFixture = `[{
		"date": "2024-09-28", "symbol": "AAPL", "reported_currency": "USD", "cik": "0000320193",
		"fiscal_year": "2024", "period": "FY",
		"net_income": "93736000000", "operating_cash_flow": "118254000000",
		"investing_cash_flow": "2935000000", "financing_cash_flow": "-121983000000",
		"capital_expenditure": "-9447000000", "free_cash_flow": "108807000000",
		"dividends_paid": "-15234000000", "stock_based_compensation": "11688000000",
		"cash_change": "-7946000000"
	}]`
)

func TestDecodeStatementListPreservesFields(t *testing.T) {
	t.Run("statement fixtures decode to raw messages", func(t *testing.T) {
		for _, stmt := range []struct {
			name    string
			fixture string
		}{
			{statementIncome, incomeStatementFixture},
			{statementBalance, balanceSheetFixture},
			{statementCashflow, cashFlowStatementFixture},
		} {
			items, err := decodeStatementList([]byte(stmt.fixture), stmt.name)
			if err != nil {
				t.Fatalf("decodeStatementList(%s): %v", stmt.name, err)
			}
			if len(items) != 1 {
				t.Fatalf("decodeStatementList(%s) len = %d, want 1", stmt.name, len(items))
			}
		}
	})

	t.Run("tolerates and preserves unknown fields", func(t *testing.T) {
		raw := `[{"date": "2024-09-28", "symbol": "AAPL", "custom_line_item": "100"}]`
		items, err := decodeStatementList([]byte(raw), statementIncome)
		if err != nil {
			t.Fatalf("decodeStatementList failed on unknown field: %v", err)
		}
		if len(items) != 1 {
			t.Fatalf("unexpected items count: %d", len(items))
		}
		var item map[string]json.RawMessage
		if err := json.Unmarshal(items[0], &item); err != nil {
			t.Fatalf("unmarshal item: %v", err)
		}
		if string(item["date"]) != `"2024-09-28"` || string(item["symbol"]) != `"AAPL"` {
			t.Errorf("header fields corrupted: %+v", item)
		}
		if string(item["custom_line_item"]) != `"100"` {
			t.Errorf("custom_line_item = %s, want %q", item["custom_line_item"], `"100"`)
		}
	})

	t.Run("missing header fields fails", func(t *testing.T) {
		cases := []struct {
			name string
			raw  string
		}{
			{"missing headers", `[{"revenue":"1"}]`},
			{"missing symbol", `[{"date":"2024-09-28"}]`},
			{"missing date", `[{"symbol":"AAPL"}]`},
			{"null date", `[{"date":null,"symbol":"AAPL"}]`},
			{"empty date", `[{"date":"","symbol":"AAPL"}]`},
			{"null symbol", `[{"date":"2024-09-28","symbol":null}]`},
			{"empty symbol", `[{"date":"2024-09-28","symbol":""}]`},
		}
		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				if _, err := decodeStatementList([]byte(tc.raw), statementIncome); err == nil {
					t.Errorf("raw %s decoded, want error", tc.raw)
				}
			})
		}
	})

	t.Run("unknown statement fails", func(t *testing.T) {
		if _, err := decodeStatementList([]byte(incomeStatementFixture), "metrics"); err == nil {
			t.Error("unknown statement decoded, want error")
		}
	})
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

func TestRankSymbolMatches(t *testing.T) {
	t.Run("tier 1 exact symbol on preferred exchange beats earlier matches", func(t *testing.T) {
		// Acceptance criterion 2:
		// [SHOPX/NYSE, SHOP/NYSE, SHOP/TSX] and query="shop", exchange="TSX" =>
		// best_match.symbol == "SHOP" with exchange_short_name == "TSX", and
		// alternatives contain the other two in backend order.
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPX","name":"Shopify X","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify CA","exchange_short_name":"TSX"}`),
		}

		best, alts, err := rankSymbolMatches(items, "shop", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" || bestItem["exchange_short_name"] != "TSX" {
			t.Errorf("bestItem = %+v, want SHOP/TSX", bestItem)
		}

		if len(alts) != 2 {
			t.Fatalf("len(alts) = %d, want 2", len(alts))
		}
		var alt0, alt1 map[string]any
		if err := json.Unmarshal(alts[0], &alt0); err != nil {
			t.Fatalf("unmarshal alt0: %v", err)
		}
		if err := json.Unmarshal(alts[1], &alt1); err != nil {
			t.Fatalf("unmarshal alt1: %v", err)
		}
		if alt0["symbol"] != "SHOPX" || alt0["exchange_short_name"] != "NYSE" {
			t.Errorf("alt0 = %+v, want SHOPX/NYSE", alt0)
		}
		if alt1["symbol"] != "SHOP" || alt1["exchange_short_name"] != "NYSE" {
			t.Errorf("alt1 = %+v, want SHOP/NYSE", alt1)
		}
	})

	t.Run("tier 2 exact symbol match anywhere beats earlier partial match without exchange", func(t *testing.T) {
		// Acceptance criterion 3:
		// Without exchange, an exact symbol match beats an earlier partial match.
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPPING","name":"Shopping Inc","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" {
			t.Errorf("bestItem symbol = %v, want SHOP", bestItem["symbol"])
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
		var altItem map[string]any
		if err := json.Unmarshal(alts[0], &altItem); err != nil {
			t.Fatalf("unmarshal alt: %v", err)
		}
		if altItem["symbol"] != "SHOPPING" {
			t.Errorf("altItem symbol = %v, want SHOPPING", altItem["symbol"])
		}
	})

	t.Run("tier 2 exact symbol match anywhere beats tier 3 partial match on preferred exchange", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPPING","name":"Shopping CA","exchange_short_name":"TSX"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" || bestItem["exchange_short_name"] != "NYSE" {
			t.Errorf("bestItem = %+v, want SHOP/NYSE", bestItem)
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
	})

	t.Run("tier 3 first result on preferred exchange beats earlier partial match on other exchange", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOP-US","name":"Shop US","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP-CA1","name":"Shop CA 1","exchange_short_name":"TSX"}`),
			json.RawMessage(`{"symbol":"SHOP-CA2","name":"Shop CA 2","exchange_short_name":"TSX"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP-CA1" {
			t.Errorf("bestItem symbol = %v, want SHOP-CA1", bestItem["symbol"])
		}
		if len(alts) != 2 {
			t.Fatalf("len(alts) = %d, want 2", len(alts))
		}
	})

	t.Run("tier 4 first result when preferred exchange matches nothing", func(t *testing.T) {
		// Risk mitigation: if preferred exchange matches nothing, fall back cleanly to tier 4
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOP-A","name":"Shop A","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP-B","name":"Shop B","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "xyz", "LSE")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP-A" {
			t.Errorf("bestItem symbol = %v, want SHOP-A", bestItem["symbol"])
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
	})

	t.Run("capping alternatives at max 10", func(t *testing.T) {
		// Acceptance criterion 4:
		// With 15 backend results, alternatives has 10 items.
		items := make([]json.RawMessage, 15)
		for i := 0; i < 15; i++ {
			items[i] = json.RawMessage(fmt.Sprintf(`{"symbol":"SYM%d","exchange_short_name":"NYSE"}`, i))
		}

		best, alts, err := rankSymbolMatches(items, "query", "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SYM0" {
			t.Errorf("bestItem symbol = %v, want SYM0", bestItem["symbol"])
		}
		if len(alts) != 10 {
			t.Fatalf("len(alts) = %d, want 10", len(alts))
		}
	})

	t.Run("single result yields empty alternatives slice", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"AAPL","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "AAPL", "NASDAQ")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if best == nil {
			t.Fatal("expected non-nil best")
		}
		if len(alts) != 0 {
			t.Fatalf("len(alts) = %d, want 0", len(alts))
		}
		out, err := json.Marshal(resolveSymbolResult{BestMatch: best, Alternatives: alts})
		if err != nil {
			t.Fatalf("marshal resolveSymbolResult: %v", err)
		}
		if !strings.Contains(string(out), `"alternatives":[]`) {
			t.Errorf("expected alternatives:[], got: %s", string(out))
		}
	})

	t.Run("unknown fields pass through unchanged", func(t *testing.T) {
		// Acceptance criterion 6:
		// Unknown fields on result items pass through unchanged.
		rawItem := `{"symbol":"SHOP","exchange_short_name":"TSX","custom_field":"hello","nested":{"key":123}}`
		items := []json.RawMessage{
			json.RawMessage(rawItem),
		}

		best, _, err := rankSymbolMatches(items, "shop", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if string(best) != rawItem {
			t.Errorf("best = %s, want %s", string(best), rawItem)
		}
	})

	t.Run("empty items returns ErrNoData", func(t *testing.T) {
		_, _, err := rankSymbolMatches([]json.RawMessage{}, "shop", "TSX")
		if !errors.Is(err, ErrNoData) {
			t.Fatalf("expected ErrNoData, got: %v", err)
		}
	})

	t.Run("malformed json returns ErrProvider", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`not-json`),
		}
		_, _, err := rankSymbolMatches(items, "shop", "TSX")
		if !errors.Is(err, ErrProvider) {
			t.Fatalf("expected ErrProvider, got: %v", err)
		}
	})
}

func TestResolveSymbolToolIntegration(t *testing.T) {
	t.Run("unsupported exchange rejected before backend call", func(t *testing.T) {
		// Acceptance criterion 5:
		// An unsupported exchange is rejected before any backend call (T01 validator)
		backendCalls := 0
		backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			backendCalls++
			w.WriteHeader(http.StatusOK)
		}))
		defer backend.Close()

		session := newTestSession(t, backend.URL)
		res := callTool(t, session, "resolve_symbol", map[string]any{
			"query":    "apple",
			"exchange": "INVALID",
		})
		if !res.IsError {
			t.Fatal("expected error result for unsupported exchange")
		}
		if backendCalls != 0 {
			t.Errorf("backend calls = %d, want 0", backendCalls)
		}
		msg := resultText(t, res)
		if !strings.Contains(msg, "exchange must be one of") {
			t.Errorf("error text = %q, want exchange must be one of", msg)
		}
	})

	t.Run("backend 404 yields no-data result", func(t *testing.T) {
		// Acceptance criterion 5:
		// backend 404 still yields the no-data result
		backend, _ := newStubBackend(t, http.StatusNotFound, `{"detail":"No market data found for 'unknown'."}`)
		session := newTestSession(t, backend.URL)

		res := callTool(t, session, "resolve_symbol", map[string]any{"query": "unknown"})
		if res.IsError {
			t.Fatalf("expected successful no-data result, got error: %s", resultText(t, res))
		}
		msg := resultText(t, res)
		if msg != noDataMessage {
			t.Errorf("result text = %q, want %q", msg, noDataMessage)
		}
	})

	t.Run("end to end ranking and unknown fields pass-through", func(t *testing.T) {
		// Acceptance criteria 2 and 6 end-to-end
		fixture := `[
			{"symbol":"SHOPX","name":"Shopify X","exchange_short_name":"NYSE","custom_score":10},
			{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE","custom_score":20},
			{"symbol":"SHOP","name":"Shopify CA","exchange_short_name":"TSX","custom_score":30}
		]`
		backend, captured := newStubBackend(t, http.StatusOK, fixture)
		session := newTestSession(t, backend.URL)

		res := callTool(t, session, "resolve_symbol", map[string]any{
			"query":    "shop",
			"exchange": "TSX",
		})
		if res.IsError {
			t.Fatalf("callTool failed: %s", resultText(t, res))
		}

		if captured.path != "/api/v1/market/data/symbols/search" {
			t.Errorf("path = %q, want /api/v1/market/data/symbols/search", captured.path)
		}
		if captured.query.Get("q") != "shop" {
			t.Errorf("query q = %q, want shop", captured.query.Get("q"))
		}

		var payload struct {
			BestMatch    map[string]any   `json:"best_match"`
			Alternatives []map[string]any `json:"alternatives"`
		}
		if err := json.Unmarshal([]byte(resultText(t, res)), &payload); err != nil {
			t.Fatalf("unmarshal payload: %v", err)
		}

		if payload.BestMatch["symbol"] != "SHOP" || payload.BestMatch["exchange_short_name"] != "TSX" {
			t.Errorf("best match = %+v, want SHOP/TSX", payload.BestMatch)
		}
		if payload.BestMatch["custom_score"] != float64(30) {
			t.Errorf("custom_score = %v, want 30", payload.BestMatch["custom_score"])
		}

		if len(payload.Alternatives) != 2 {
			t.Fatalf("len(alternatives) = %d, want 2", len(payload.Alternatives))
		}
		if payload.Alternatives[0]["symbol"] != "SHOPX" || payload.Alternatives[0]["custom_score"] != float64(10) {
			t.Errorf("alt 0 = %+v", payload.Alternatives[0])
		}
		if payload.Alternatives[1]["symbol"] != "SHOP" || payload.Alternatives[1]["custom_score"] != float64(20) {
			t.Errorf("alt 1 = %+v", payload.Alternatives[1])
		}
	})
}

func TestGetPriceHistory_OptionalDatesAndInterval(t *testing.T) {
	var capturedQuery url.Values
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedQuery = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"symbol":"AAPL","currency":"USD","from_date":"2023-01-01","to_date":"2024-01-01","interval":"day","items":[]}`))
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	t.Run("without from and to sends neither parameter", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol": "AAPL",
		})
		if res.IsError {
			t.Fatalf("unexpected tool error: %v", resultText(t, res))
		}
		if capturedQuery == nil {
			t.Fatal("backend was not called")
		}
		if capturedQuery.Has("from") {
			t.Errorf("expected no 'from' param, got %q", capturedQuery.Get("from"))
		}
		if capturedQuery.Has("to") {
			t.Errorf("expected no 'to' param, got %q", capturedQuery.Get("to"))
		}
		if capturedQuery.Has("interval") {
			t.Errorf("expected no 'interval' param when empty, got %q", capturedQuery.Get("interval"))
		}
	})

	t.Run("with interval sends interval parameter", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol":   "AAPL",
			"interval": "week",
		})
		if res.IsError {
			t.Fatalf("unexpected tool error: %v", resultText(t, res))
		}
		if capturedQuery.Get("interval") != "week" {
			t.Errorf("expected interval=week, got %q", capturedQuery.Get("interval"))
		}
		if capturedQuery.Has("from") || capturedQuery.Has("to") {
			t.Errorf("expected neither from nor to, got from=%q to=%q", capturedQuery.Get("from"), capturedQuery.Get("to"))
		}
	})

	t.Run("interval validated client-side", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol":   "AAPL",
			"interval": "biweekly",
		})
		if !res.IsError {
			t.Fatal("expected error on invalid interval")
		}
		if capturedQuery != nil {
			t.Fatal("backend should not have been called for invalid interval")
		}
		if !strings.Contains(resultText(t, res), "interval must be 'day', 'week', or 'month'") {
			t.Errorf("expected interval error message, got %q", resultText(t, res))
		}
	})
}

func TestGetPriceHistory_Backend422CapErrorForwardedToAgent(t *testing.T) {
	const capErrorMessage = "Requested range spans ~2609 bars, exceeding the limit of 2000. Narrow the date range or use a coarser interval ('week' or 'month')."
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"detail": capErrorMessage,
		})
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	res := callTool(t, session, "get_price_history", map[string]any{
		"symbol": "AAPL",
		"from":   "2015-01-01",
		"to":     "2024-12-31",
	})
	if !res.IsError {
		t.Fatal("expected tool error on backend 422")
	}
	text := resultText(t, res)
	if !strings.Contains(text, capErrorMessage) {
		t.Errorf("expected backend 422 message %q forwarded to agent, got %q", capErrorMessage, text)
	}
}

func TestGetTechnicalIndicator_ClientSideValidationAndPassThrough(t *testing.T) {
	var capturedQuery url.Values
	var capturedPath string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		capturedQuery = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"symbol":"AAPL","indicator":"bollinger","currency":"USD","from_date":"2026-01-01","to_date":"2026-01-31","params":{"period":20,"std_dev":2},"points":[{"time":"2026-01-02","value":100.0}]}`))
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	t.Run("client-side validation rejects invalid indicator before backend", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "unknown",
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for invalid indicator")
		}
		if !strings.Contains(resultText(t, res), "indicator must be 'sma', 'ema', 'rsi', 'macd', or 'bollinger'") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range period", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "rsi",
			"period":    1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for period < 2")
		}
		if !strings.Contains(resultText(t, res), "period must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range fast", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"fast":      1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for fast < 2")
		}
		if !strings.Contains(resultText(t, res), "fast must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range slow", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"slow":      401,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for slow > 400")
		}
		if !strings.Contains(resultText(t, res), "slow must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range signal", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"signal":    1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for signal < 2")
		}
		if !strings.Contains(resultText(t, res), "signal must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects non-positive std_dev", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "bollinger",
			"std_dev":   0,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for std_dev <= 0")
		}
		if !strings.Contains(resultText(t, res), "std_dev must be greater than 0") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("sends query and passes json through", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "aapl",
			"indicator": "bollinger",
			"period":    20,
			"std_dev":   2.0,
			"from":      "2026-01-01",
			"to":        "2026-01-31",
			"exchange":  "nasdaq",
		})
		if res.IsError {
			t.Fatalf("unexpected error: %s", resultText(t, res))
		}
		if capturedPath != "/api/v1/market/data/indicators/AAPL" {
			t.Errorf("captured path = %q, want /api/v1/market/data/indicators/AAPL", capturedPath)
		}
		if capturedQuery.Get("indicator") != "bollinger" {
			t.Errorf("indicator = %q, want bollinger", capturedQuery.Get("indicator"))
		}
		if capturedQuery.Get("period") != "20" {
			t.Errorf("period = %q, want 20", capturedQuery.Get("period"))
		}
		if capturedQuery.Get("std_dev") != "2" {
			t.Errorf("std_dev = %q, want 2", capturedQuery.Get("std_dev"))
		}
		if capturedQuery.Get("exchange") != "NASDAQ" {
			t.Errorf("exchange = %q, want NASDAQ", capturedQuery.Get("exchange"))
		}
		raw := resultText(t, res)
		if !strings.Contains(raw, `"points"`) || !strings.Contains(raw, `"currency":"USD"`) {
			t.Errorf("expected passthrough JSON, got: %s", raw)
		}
	})
}
