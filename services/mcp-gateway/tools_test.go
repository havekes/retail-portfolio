package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"sort"
	"strings"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// expectedToolNames is the exact, provider-agnostic tool set this ticket
// registers. Order is irrelevant; tests compare as a set.
var expectedToolNames = []string{
	"get_price_history",
	"get_fundamentals",
	"get_options_chain",
	"get_income_statement",
	"get_balance_sheet",
	"get_cash_flow_statement",
	"get_key_metrics",
	"get_financial_ratios",
	"get_company_details",
	"search_symbols",
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
	srv := httptest.NewServer(newRouter(newMCPServer(client, Config{Environment: "dev"})))
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
		}]
	}`

	symbolSearchBody = `[{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}]`

	incomeStatementBody   = `[{"date": "2024-09-28", "symbol": "AAPL", "revenue": "391035000000"}]`
	balanceSheetBody      = `[{"date": "2024-09-28", "symbol": "AAPL", "total_assets": "364980000000"}]`
	cashFlowStatementBody = `[{"date": "2024-09-28", "symbol": "AAPL", "operating_cash_flow": "118254000000"}]`
)

// toolCall is a valid invocation of one tool.
type toolCall struct {
	tool string
	args map[string]any
}

var validToolCalls = []toolCall{
	{"get_price_history", map[string]any{"symbol": "AAPL", "from": "2026-01-01", "to": "2026-01-31"}},
	{"get_fundamentals", map[string]any{"symbol": "AAPL"}},
	{"get_options_chain", map[string]any{"symbol": "AAPL"}},
	{"get_income_statement", map[string]any{"symbol": "AAPL"}},
	{"get_balance_sheet", map[string]any{"symbol": "AAPL"}},
	{"get_cash_flow_statement", map[string]any{"symbol": "AAPL"}},
	{"get_key_metrics", map[string]any{"symbol": "AAPL"}},
	{"get_financial_ratios", map[string]any{"symbol": "AAPL"}},
	{"get_company_details", map[string]any{"symbol": "AAPL"}},
	{"search_symbols", map[string]any{"q": "apple"}},
}

// statementPayload is the decoded shape of the statement tools' envelope.
type statementPayload struct {
	Statement string `json:"statement"`
	Symbol    string `json:"symbol"`
	Period    string `json:"period"`
	Limit     int    `json:"limit"`
	Exchange  string `json:"exchange"`
	Items     []struct {
		Date              string  `json:"date"`
		Symbol            string  `json:"symbol"`
		Revenue           Decimal `json:"revenue"`
		TotalAssets       Decimal `json:"total_assets"`
		OperatingCashFlow Decimal `json:"operating_cash_flow"`
	} `json:"items"`
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
				"from": "2026-01-01", "to": "2026-01-31", "exchange": "nasdaq",
			},
			assert: func(t *testing.T, raw string) {
				var got struct {
					Symbol string `json:"symbol"`
					Items  []struct {
						Close Decimal `json:"close"`
					} `json:"items"`
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode PriceHistory: %v", err)
				}
				if got.Symbol != "AAPL" || len(got.Items) != 1 || got.Items[0].Close != Decimal("154") {
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
			wantQuery: map[string]string{"exchange": "nasdaq"},
			assert: func(t *testing.T, raw string) {
				var got CompanyFundamentals
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode CompanyFundamentals: %v", err)
				}
				if got.Profile.CompanyName != "Apple Inc." {
					t.Errorf("company_name = %q", got.Profile.CompanyName)
				}
				if got.KeyMetrics.PERatio == nil || *got.KeyMetrics.PERatio != Decimal("36.28") {
					t.Errorf("pe_ratio = %v", got.KeyMetrics.PERatio)
				}
				if got.Ratios.DebtToEquity == nil || *got.Ratios.DebtToEquity != Decimal("1.87") {
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
				}
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode OptionsChain: %v", err)
				}
				if got.UnderlyingSymbol != "AAPL" || len(got.Contracts) != 1 {
					t.Errorf("payload = %+v", got)
				}
			},
		},
		{
			name:     "get_income_statement",
			tool:     "get_income_statement",
			args:     map[string]any{"symbol": "aapl", "period": "quarter", "limit": 3, "exchange": "nasdaq"},
			body:     incomeStatementBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL/statements",
			wantQuery: map[string]string{
				"statement": "income", "period": "quarter", "limit": "3", "exchange": "nasdaq",
			},
			assert: func(t *testing.T, raw string) {
				var got statementPayload
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode statement envelope: %v", err)
				}
				if got.Statement != "income" || got.Symbol != "aapl" || got.Period != "quarter" || got.Limit != 3 {
					t.Errorf("envelope = %+v", got)
				}
				if len(got.Items) != 1 || got.Items[0].Revenue != Decimal("391035000000") {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_balance_sheet defaults",
			tool:     "get_balance_sheet",
			args:     map[string]any{"symbol": "aapl"},
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
				if len(got.Items) != 1 || got.Items[0].TotalAssets != Decimal("364980000000") {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_cash_flow_statement clamps limit",
			tool:     "get_cash_flow_statement",
			args:     map[string]any{"symbol": "aapl", "limit": 25},
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
				if len(got.Items) != 1 || got.Items[0].OperatingCashFlow != Decimal("118254000000") {
					t.Errorf("items = %+v", got.Items)
				}
			},
		},
		{
			name:     "get_key_metrics projects key_metrics",
			tool:     "get_key_metrics",
			args:     map[string]any{"symbol": "aapl"},
			body:     fundamentalsBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL",
			assert: func(t *testing.T, raw string) {
				var got KeyMetrics
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode KeyMetrics: %v", err)
				}
				if got.PERatio == nil || *got.PERatio != Decimal("36.28") {
					t.Errorf("pe_ratio = %v", got.PERatio)
				}
			},
		},
		{
			name:     "get_financial_ratios projects ratios",
			tool:     "get_financial_ratios",
			args:     map[string]any{"symbol": "aapl"},
			body:     fundamentalsBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL",
			assert: func(t *testing.T, raw string) {
				var got FinancialRatios
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode FinancialRatios: %v", err)
				}
				if got.DebtToEquity == nil || *got.DebtToEquity != Decimal("1.87") {
					t.Errorf("debt_to_equity = %v", got.DebtToEquity)
				}
			},
		},
		{
			name:     "get_company_details projects profile",
			tool:     "get_company_details",
			args:     map[string]any{"symbol": "aapl"},
			body:     fundamentalsBody,
			wantPath: "/api/v1/market/data/fundamentals/AAPL",
			assert: func(t *testing.T, raw string) {
				var got CompanyProfile
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode CompanyProfile: %v", err)
				}
				if got.CompanyName != "Apple Inc." {
					t.Errorf("company_name = %q", got.CompanyName)
				}
			},
		},
		{
			name:      "search_symbols",
			tool:      "search_symbols",
			args:      map[string]any{"q": "apple"},
			body:      symbolSearchBody,
			wantPath:  "/api/v1/market/data/symbols/search",
			wantQuery: map[string]string{"q": "apple"},
			assert: func(t *testing.T, raw string) {
				var got []map[string]any
				if err := json.Unmarshal([]byte(raw), &got); err != nil {
					t.Fatalf("decode search results: %v", err)
				}
				if len(got) != 1 || got[0]["symbol"] != "AAPL" {
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
	backend, _ := newStubBackend(t, http.StatusOK, `[{"revenue":"1"}]`)
	session := newTestSession(t, backend.URL)

	result := callTool(t, session, "get_income_statement", map[string]any{"symbol": "AAPL"})
	if !result.IsError {
		t.Fatalf("expected an error result, got %q", resultText(t, result))
	}
	if got := resultText(t, result); got != "tool call failed" {
		t.Errorf("result text = %q, want %q", got, "tool call failed")
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
			name: "bad period",
			prepare: func() error {
				_, err := (statementInput{Symbol: "AAPL", Period: "monthly"}).prepare()
				return err
			},
			want: "period must be 'annual' or 'quarter'",
		},
		{
			name: "bad option type",
			prepare: func() error {
				_, err := (optionsChainInput{Symbol: "AAPL", OptionType: "straddle"}).prepare()
				return err
			},
			want: "option_type must be 'call' or 'put'",
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
				_, err := (optionsChainInput{Symbol: "AAPL", StrikeMin: &min, StrikeMax: &max}).prepare()
				return err
			},
			want: "strike_min must be on or before strike_max",
		},
		{
			name: "empty query",
			prepare: func() error {
				_, err := (searchSymbolsInput{Query: "   "}).prepare()
				return err
			},
			want: "q must be between 1 and 100 characters",
		},
		{
			name: "query too long",
			prepare: func() error {
				_, err := (searchSymbolsInput{Query: strings.Repeat("a", maxQueryLength+1)}).prepare()
				return err
			},
			want: "q must be between 1 and 100 characters",
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
		in   statementInput
		want int
		per  string
	}{
		{statementInput{Symbol: "AAPL", Limit: 0}, 5, "annual"},
		{statementInput{Symbol: "AAPL", Limit: -3}, 5, "annual"},
		{statementInput{Symbol: "AAPL", Limit: 25}, 20, "annual"},
		{statementInput{Symbol: "AAPL", Limit: 3}, 3, "annual"},
		{statementInput{Symbol: "AAPL", Period: "quarter"}, 5, "quarter"},
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

	// `from`/`to` are non-omitempty, so the SDK rejects the call before the
	// handler runs.
	result := callTool(t, session, "get_price_history", map[string]any{"symbol": "AAPL"})
	if !result.IsError {
		t.Fatalf("expected the SDK to reject a missing required argument, got %q", resultText(t, result))
	}
}

// Full statement fixtures: every key equals exactly the corresponding Go
// struct's JSON field set (T09 carry-over).
const (
	incomeStatementFixture = `[{
		"date": "2024-09-28", "symbol": "AAPL", "reported_currency": "USD", "cik": "0000320193",
		"filling_date": "2024-11-01", "accepted_date": "2024-11-01T06:01:27.000Z",
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

func TestDecodeStatementListFieldSetContract(t *testing.T) {
	t.Run("fixtures match the struct JSON field sets", func(t *testing.T) {
		checks := []struct {
			fixture string
			typ     reflect.Type
		}{
			{incomeStatementFixture, reflect.TypeFor[IncomeStatement]()},
			{balanceSheetFixture, reflect.TypeFor[BalanceSheet]()},
			{cashFlowStatementFixture, reflect.TypeFor[CashFlowStatement]()},
		}
		for _, check := range checks {
			got := fixtureKeys(t, check.fixture)
			want := structJSONFields(check.typ)
			if !reflect.DeepEqual(got, want) {
				t.Errorf("%s fixture keys = %v, want %v", check.typ, got, want)
			}
		}
	})

	t.Run("decodes to the statement-specific type", func(t *testing.T) {
		if _, ok := mustDecodeStatements(t, incomeStatementFixture, statementIncome).([]IncomeStatement); !ok {
			t.Error("income fixture did not decode to []IncomeStatement")
		}
		if _, ok := mustDecodeStatements(t, balanceSheetFixture, statementBalance).([]BalanceSheet); !ok {
			t.Error("balance fixture did not decode to []BalanceSheet")
		}
		if _, ok := mustDecodeStatements(t, cashFlowStatementFixture, statementCashflow).([]CashFlowStatement); !ok {
			t.Error("cashflow fixture did not decode to []CashFlowStatement")
		}
	})

	t.Run("tolerates unknown fields", func(t *testing.T) {
		raw := `[{"date": "2024-09-28", "symbol": "AAPL", "custom_line_item": "100"}]`
		items, err := decodeStatementList([]byte(raw), statementIncome)
		if err != nil {
			t.Fatalf("decodeStatementList failed on unknown field: %v", err)
		}
		incomeItems, ok := items.([]IncomeStatement)
		if !ok || len(incomeItems) != 1 {
			t.Fatalf("unexpected items: %+v", items)
		}
		if incomeItems[0].Date != "2024-09-28" || incomeItems[0].Symbol != "AAPL" {
			t.Errorf("decoded item = %+v", incomeItems[0])
		}
	})

	t.Run("missing header fields fails", func(t *testing.T) {
		if _, err := decodeStatementList([]byte(`[{"revenue":"1"}]`), statementIncome); err == nil {
			t.Error("item missing date/symbol decoded, want error")
		}
	})

	t.Run("unknown statement fails", func(t *testing.T) {
		if _, err := decodeStatementList([]byte(incomeStatementFixture), "metrics"); err == nil {
			t.Error("unknown statement decoded, want error")
		}
	})
}

func mustDecodeStatements(t *testing.T, raw, statement string) any {
	t.Helper()
	items, err := decodeStatementList([]byte(raw), statement)
	if err != nil {
		t.Fatalf("decodeStatementList(%s): %v", statement, err)
	}
	return items
}

// fixtureKeys returns the sorted top-level keys of the first element of a JSON
// array fixture.
func fixtureKeys(t *testing.T, fixture string) []string {
	t.Helper()
	var items []map[string]json.RawMessage
	if err := json.Unmarshal([]byte(fixture), &items); err != nil {
		t.Fatalf("fixture is not a JSON array: %v", err)
	}
	if len(items) == 0 {
		t.Fatal("fixture is empty")
	}
	keys := make([]string, 0, len(items[0]))
	for key := range items[0] {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

// structJSONFields returns the sorted JSON names declared on a struct type.
func structJSONFields(typ reflect.Type) []string {
	fields := make([]string, 0, typ.NumField())
	for i := 0; i < typ.NumField(); i++ {
		name := strings.Split(typ.Field(i).Tag.Get("json"), ",")[0]
		if name == "" || name == "-" {
			continue
		}
		fields = append(fields, name)
	}
	sort.Strings(fields)
	return fields
}

func newTestSessionWithEnv(t *testing.T, backendURL, env string) *mcp.ClientSession {
	t.Helper()
	client := mustClient(t, backendURL, "test-token", env)
	srv := httptest.NewServer(newRouter(newMCPServer(client, Config{Environment: env})))
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
}
