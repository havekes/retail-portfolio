package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	sectionProfile    = "profile"
	sectionKeyMetrics = "key_metrics"
	sectionRatios     = "ratios"
)

const (
	descGetFundamentals = `Company profile, key valuation metrics, and financial ratios for a security in a single payload.

Use when:
Evaluating business overview, valuation multiples (P/E, EV/EBITDA), or financial ratios (margins, ROE, debt-to-equity). Requests can select any subset of 'profile', 'key_metrics', and 'ratios' (defaults to all three).

Examples:
- "Company profile and financial ratios for Nvidia" -> {"symbol": "NVDA", "sections": ["profile", "ratios"]}
- "Key metrics for Shopify on TSX" -> {"symbol": "SHOP", "sections": ["key_metrics"], "exchange": "TSX"}

Returns:
Object containing requested section objects:
- profile: company overview, sector, industry, description, and currency.
- key_metrics: valuation and operational metrics (may be null if unavailable).
- ratios: profitability and leverage ratios (may be null if unavailable).
Monetary values are decimal strings in the reporting currency.

See also:
get_financial_statements, get_quote, resolve_symbol`

	descGetFinancialStatements = `Audited financial statements (income statement, balance sheet, or cash flow statement) across reporting periods.

Use when:
Reviewing line-item financial history, revenue trends, balance sheet health, or cash flows across annual or quarterly periods.

Examples:
- "Last 3 annual income statements for Alphabet" -> {"symbol": "GOOGL", "statement": "income", "period": "annual", "limit": 3}
- "Quarterly balance sheets for Microsoft" -> {"symbol": "MSFT", "statement": "balance", "period": "quarter", "limit": 4}

Returns:
Top-level fields:
- statement: requested statement type ('income', 'balance', or 'cashflow').
- symbol: ticker symbol.
- period: reporting period ('annual' or 'quarter').
- limit: maximum periods returned (1-20).
- exchange: exchange code if filtered.
- items: array of statement period objects. Monetary line items are decimal strings in the reporting currency.

See also:
get_fundamentals, get_quote, resolve_symbol`
)

// registerFundamentalsTools attaches fundamentals and financial statement tools to server.
func registerFundamentalsTools(server *mcp.Server, client *BackendClient, cfg Config) {
	addTool(server, toolSpec{
		Name:        "get_fundamentals",
		Title:       "Get Fundamentals",
		Description: descGetFundamentals,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in fundamentalsInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_fundamentals", cfg, in, fundamentalsInput.prepare, func(ctx context.Context, r fundamentalsRequest) (any, error) {
			raw, err := client.Fundamentals(ctx, r.symbol, r.exchange)
			if err != nil {
				return nil, err
			}
			return filterFundamentalsSections(raw, r.sections)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_financial_statements",
		Title:       "Get Financial Statements",
		Description: descGetFinancialStatements,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in financialStatementsInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_financial_statements", cfg, in, financialStatementsInput.prepare, func(ctx context.Context, r financialStatementsRequest) (any, error) {
			raw, err := client.Statements(ctx, r.symbol, r.statement, r.period, r.limit, r.exchange)
			if err != nil {
				return nil, err
			}
			items, err := decodeStatementList(raw, r.statement)
			if err != nil {
				return nil, err
			}
			return statementEnvelope{
				Statement: r.statement,
				Symbol:    r.symbol,
				Period:    r.period,
				Limit:     r.limit,
				Exchange:  r.exchange,
				Items:     items,
			}, nil
		})
	})
}

// filterFundamentalsSections filters the raw fundamentals JSON aggregate to
// only the requested sections. If every requested section is null or absent,
// it returns ErrNoData.
func filterFundamentalsSections(raw json.RawMessage, requestedSections []string) (map[string]json.RawMessage, error) {
	var sections map[string]json.RawMessage
	if err := json.Unmarshal(raw, &sections); err != nil {
		return nil, &backendError{class: ErrProvider, detail: err.Error()}
	}

	out := make(map[string]json.RawMessage, len(requestedSections))
	allNullOrAbsent := true

	for _, key := range requestedSections {
		val, ok := sections[key]
		if !ok || len(val) == 0 || bytes.Equal(bytes.TrimSpace(val), []byte("null")) {
			out[key] = json.RawMessage("null")
		} else {
			out[key] = val
			allNullOrAbsent = false
		}
	}

	if allNullOrAbsent {
		return nil, &backendError{class: ErrNoData}
	}
	return out, nil
}

type fundamentalsInput struct {
	Symbol   string   `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Sections []string `json:"sections,omitempty" jsonschema:"Optional sections to include: 'profile', 'key_metrics', 'ratios' (default all)."`
	Exchange string   `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type fundamentalsRequest struct {
	symbol   string
	sections []string
	exchange string
}

func (in fundamentalsInput) prepare() (fundamentalsRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return fundamentalsRequest{}, err
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return fundamentalsRequest{}, err
	}
	sections, err := validateFundamentalsSections(in.Sections)
	if err != nil {
		return fundamentalsRequest{}, err
	}
	return fundamentalsRequest{symbol: symbol, sections: sections, exchange: exchange}, nil
}

type financialStatementsInput struct {
	Symbol    string `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Statement string `json:"statement" jsonschema:"Statement type: 'income', 'balance', or 'cashflow'."`
	Period    string `json:"period,omitempty" jsonschema:"Optional reporting period: 'annual' (default) or 'quarter'."`
	Limit     int    `json:"limit,omitempty" jsonschema:"Optional maximum number of periods to return (1-20, default 5)."`
	Exchange  string `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type financialStatementsRequest struct {
	symbol    string
	statement string
	period    string
	limit     int
	exchange  string
}

func (in financialStatementsInput) prepare() (financialStatementsRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return financialStatementsRequest{}, err
	}
	statement, err := validateStatementType(in.Statement)
	if err != nil {
		return financialStatementsRequest{}, err
	}
	period, err := normalizePeriod(in.Period)
	if err != nil {
		return financialStatementsRequest{}, err
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return financialStatementsRequest{}, err
	}
	return financialStatementsRequest{
		symbol:    symbol,
		statement: statement,
		period:    period,
		limit:     clampLimit(in.Limit),
		exchange:  exchange,
	}, nil
}

// statementEnvelope echoes the request scope alongside the decoded items.
type statementEnvelope struct {
	Statement string            `json:"statement"`
	Symbol    string            `json:"symbol"`
	Period    string            `json:"period"`
	Limit     int               `json:"limit"`
	Exchange  string            `json:"exchange,omitempty"`
	Items     []json.RawMessage `json:"items"`
}

// validateFundamentalsSections validates that each requested section name is
// one of 'profile', 'key_metrics', or 'ratios', removes duplicates, and defaults
// to all three sections when none are specified.
func validateFundamentalsSections(sections []string) ([]string, error) {
	if len(sections) == 0 {
		return []string{sectionProfile, sectionKeyMetrics, sectionRatios}, nil
	}
	valid := map[string]bool{
		sectionProfile:    true,
		sectionKeyMetrics: true,
		sectionRatios:     true,
	}
	seen := make(map[string]bool)
	var result []string
	for _, raw := range sections {
		s := strings.ToLower(strings.TrimSpace(raw))
		if !valid[s] {
			return nil, fmt.Errorf("unknown section %q: valid sections are 'profile', 'key_metrics', 'ratios'", raw)
		}
		if !seen[s] {
			seen[s] = true
			result = append(result, s)
		}
	}
	return result, nil
}

// validateStatementType validates that statement is one of 'income', 'balance', or 'cashflow'.
func validateStatementType(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case statementIncome:
		return statementIncome, nil
	case statementBalance:
		return statementBalance, nil
	case statementCashflow:
		return statementCashflow, nil
	default:
		return "", errors.New("statement must be 'income', 'balance', or 'cashflow'")
	}
}
