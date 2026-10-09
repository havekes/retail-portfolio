package tools

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

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
			{backend.StatementIncome, incomeStatementFixture},
			{backend.StatementBalance, balanceSheetFixture},
			{backend.StatementCashflow, cashFlowStatementFixture},
		} {
			items, err := backend.DecodeStatementList([]byte(stmt.fixture), stmt.name)
			if err != nil {
				t.Fatalf("backend.DecodeStatementList(%s): %v", stmt.name, err)
			}
			if len(items) != 1 {
				t.Fatalf("backend.DecodeStatementList(%s) len = %d, want 1", stmt.name, len(items))
			}
		}
	})

	t.Run("tolerates and preserves unknown fields", func(t *testing.T) {
		raw := `[{"date": "2024-09-28", "symbol": "AAPL", "custom_line_item": "100"}]`
		items, err := backend.DecodeStatementList([]byte(raw), backend.StatementIncome)
		if err != nil {
			t.Fatalf("backend.DecodeStatementList failed on unknown field: %v", err)
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
				if _, err := backend.DecodeStatementList([]byte(tc.raw), backend.StatementIncome); err == nil {
					t.Errorf("raw %s decoded, want error", tc.raw)
				}
			})
		}
	})

	t.Run("unknown statement fails", func(t *testing.T) {
		if _, err := backend.DecodeStatementList([]byte(incomeStatementFixture), "metrics"); err == nil {
			t.Error("unknown statement decoded, want error")
		}
	})
}
