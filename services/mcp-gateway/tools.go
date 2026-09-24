package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// This file registers the provider-agnostic MCP tools. Every tool:
//
//   - declares a typed input struct (the SDK infers the input schema from it and
//     rejects calls that omit a required field before the handler runs);
//   - validates and normalizes its input in a prepare method, so most invalid
//     input is rejected before the backend is called; a backend 422 that still
//     slips through is classified as ErrValidation and surfaced as an actionable
//     error rather than "no data";
//   - calls the backend through the BackendClient and shapes the result through
//     runTool, implementing the T10 error contract.
//
// Tool names, descriptions and result text use only "market data" vocabulary:
// no upstream provider brand may appear here.

// Validation bounds. They mirror the backend data plane's query constraints
// (src/market/data_router.py) so the handlers can reject or clamp out-of-range
// input instead of letting the backend answer 422.
const (
	defaultStatementLimit = 5
	maxStatementLimit     = 20
	maxSymbolLength       = 32
	minQueryLength        = 1
	maxQueryLength        = 100
)

// noDataMessage is the successful result text used when the backend reports
// ErrNoData. A 404 can be a cached empty result within the cache TTL, so this
// is deliberately not phrased as an error or as "invalid symbol".
const noDataMessage = "No market data is available for this request."

// registerTools attaches every market-data tool to server, closing over client.
func registerTools(server *mcp.Server, client *BackendClient) {
	addTool(server, "get_price_history",
		"Daily open/high/low/close price history for a symbol over a date range, with an optional exchange filter.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in priceHistoryInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, priceHistoryInput.prepare, func(ctx context.Context, r priceHistoryRequest) (any, error) {
				return client.Prices(ctx, r.symbol, r.from, r.to, r.exchange)
			})
		})

	addTool(server, "get_fundamentals",
		"Analysis-ready fundamentals for a symbol: company profile, key metrics and financial ratios in one payload.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in fundamentalsInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, fundamentalsInput.prepare, func(ctx context.Context, r fundamentalsRequest) (any, error) {
				return client.Fundamentals(ctx, r.symbol, r.exchange)
			})
		})

	addTool(server, "get_options_chain",
		"Options chain for an underlying symbol with optional expiry, contract-type and strike filters.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in optionsChainInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, optionsChainInput.prepare, func(ctx context.Context, r optionsChainRequest) (any, error) {
				return client.OptionsChain(ctx, r.symbol, r.expiry, r.optionType, r.strikeMin, r.strikeMax)
			})
		})

	addTool(server, "get_income_statement",
		"Income statements for a symbol, optionally filtered by reporting period and limited to the most recent periods.",
		statementHandler(client, statementIncome))

	addTool(server, "get_balance_sheet",
		"Balance sheets for a symbol, optionally filtered by reporting period and limited to the most recent periods.",
		statementHandler(client, statementBalance))

	addTool(server, "get_cash_flow_statement",
		"Cash-flow statements for a symbol, optionally filtered by reporting period and limited to the most recent periods.",
		statementHandler(client, statementCashflow))

	addTool(server, "get_key_metrics",
		"Key valuation metrics for a symbol: market cap, multiples, yields and leverage ratios.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in fundamentalsInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, fundamentalsInput.prepare, func(ctx context.Context, r fundamentalsRequest) (any, error) {
				fundamentals, err := client.Fundamentals(ctx, r.symbol, r.exchange)
				if err != nil {
					return nil, err
				}
				return fundamentals.KeyMetrics, nil
			})
		})

	addTool(server, "get_financial_ratios",
		"Financial ratios for a symbol: margins, returns, liquidity and leverage.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in fundamentalsInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, fundamentalsInput.prepare, func(ctx context.Context, r fundamentalsRequest) (any, error) {
				fundamentals, err := client.Fundamentals(ctx, r.symbol, r.exchange)
				if err != nil {
					return nil, err
				}
				return fundamentals.Ratios, nil
			})
		})

	addTool(server, "get_company_details",
		"Company profile details for a symbol: name, sector, industry, employees and identifiers.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in fundamentalsInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, fundamentalsInput.prepare, func(ctx context.Context, r fundamentalsRequest) (any, error) {
				fundamentals, err := client.Fundamentals(ctx, r.symbol, r.exchange)
				if err != nil {
					return nil, err
				}
				return fundamentals.Profile, nil
			})
		})

	addTool(server, "search_symbols",
		"Search for symbols and companies by name or ticker fragment.",
		func(ctx context.Context, _ *mcp.CallToolRequest, in searchSymbolsInput) (*mcp.CallToolResult, any, error) {
			return runTool(ctx, in, searchSymbolsInput.prepare, func(ctx context.Context, r searchSymbolsRequest) (any, error) {
				return client.SymbolSearch(ctx, r.query)
			})
		})
}

// addTool is a thin wrapper over the SDK generic mcp.AddTool. Out is always any
// so the SDK never infers an output schema: results are plain JSON served as
// TextContent by the shared helpers below.
func addTool[In any](
	server *mcp.Server,
	name, description string,
	handler mcp.ToolHandlerFor[In, any],
) {
	mcp.AddTool(server, &mcp.Tool{Name: name, Description: description}, handler)
}

// statementHandler builds the handler for one statement tool. statement is
// fixed by the tool; it is never an input.
func statementHandler(client *BackendClient, statement string) mcp.ToolHandlerFor[statementInput, any] {
	return func(ctx context.Context, _ *mcp.CallToolRequest, in statementInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, in, statementInput.prepare, func(ctx context.Context, r statementRequest) (any, error) {
			raw, err := client.Statements(ctx, r.symbol, statement, r.period, r.limit, r.exchange)
			if err != nil {
				return nil, err
			}
			items, err := decodeStatementList(raw, statement)
			if err != nil {
				return nil, err
			}
			return statementEnvelope{
				Statement: statement,
				Symbol:    r.symbol,
				Period:    r.period,
				Limit:     r.limit,
				Exchange:  r.exchange,
				Items:     items,
			}, nil
		})
	}
}

// runTool is the shared handler pipeline: it validates and normalizes the typed
// input via prepare, calls the backend, and maps the outcome to an MCP result
// per the T10 error contract.
func runTool[In, Req any](
	ctx context.Context,
	in In,
	prepare func(In) (Req, error),
	doBackend func(context.Context, Req) (any, error),
) (*mcp.CallToolResult, any, error) {
	req, err := prepare(in)
	if err != nil {
		// Validation failures are synthesized locally; nothing backend-produced
		// is ever forwarded here.
		return errorResult(err), nil, nil
	}

	payload, err := doBackend(ctx, req)
	if err != nil {
		return mapBackendError(err), nil, nil
	}
	return successResult(payload)
}

// successResult serializes payload into a single TextContent block. The output
// value is nil: the result is fully shaped here.
func successResult(payload any) (*mcp.CallToolResult, any, error) {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return errorResult(errors.New("tool call failed")), nil, nil
	}
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(encoded)}},
	}, nil, nil
}

// noDataResult is a *successful* result: there is simply no data for the request
// right now.
func noDataResult() *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: noDataMessage}},
	}
}

// errorResult builds an error result from err. Only ever passed locally
// synthesized messages — including the agent-safe validation message parsed
// from a backend 422 by the client — or the generic error sentinels, whose text
// contains no status, body, token or provider detail.
func errorResult(err error) *mcp.CallToolResult {
	result := &mcp.CallToolResult{}
	result.SetError(err)
	return result
}

// mapBackendError maps a BackendClient error onto a tool result:
//
//   - ErrValidation ⇒ an error result carrying the backend's validation message
//     (falling back to the generic sentinel text), so an agent can correct its
//     parameters instead of being told there is no data;
//   - ErrNoData ⇒ a successful "no data" result;
//   - ErrConfiguration / ErrProvider ⇒ an error result carrying the generic
//     sentinel text (backendError hides the status/body detail);
//   - anything else ⇒ a generic catch-all error.
func mapBackendError(err error) *mcp.CallToolResult {
	switch {
	case errors.Is(err, ErrValidation):
		return errorResult(errors.New(validationErrorMessage(err)))
	case errors.Is(err, ErrNoData):
		return noDataResult()
	case errors.Is(err, ErrConfiguration), errors.Is(err, ErrProvider):
		return errorResult(err)
	default:
		return errorResult(errors.New("tool call failed"))
	}
}

// validationErrorMessage returns the agent-safe validation text carried by an
// ErrValidation backendError, falling back to the generic sentinel text when the
// 422 body was unparsable.
func validationErrorMessage(err error) string {
	var backendErr *backendError
	if errors.As(err, &backendErr) {
		if message := backendErr.ValidationMessage(); message != "" {
			return message
		}
	}
	return ErrValidation.Error()
}

// --------------------------------------------------------------------------- //
// Tool inputs and their validated/normalized forms
// --------------------------------------------------------------------------- //

type priceHistoryInput struct {
	Symbol   string `json:"symbol" jsonschema:"Ticker symbol of the security."`
	From     string `json:"from" jsonschema:"Start date (inclusive) in YYYY-MM-DD format."`
	To       string `json:"to" jsonschema:"End date (inclusive) in YYYY-MM-DD format."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter."`
}

type priceHistoryRequest struct {
	symbol   string
	from     time.Time
	to       time.Time
	exchange string
}

func (in priceHistoryInput) prepare() (priceHistoryRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return priceHistoryRequest{}, err
	}
	from, err := parseToolDate(in.From, "from")
	if err != nil {
		return priceHistoryRequest{}, err
	}
	to, err := parseToolDate(in.To, "to")
	if err != nil {
		return priceHistoryRequest{}, err
	}
	if from.After(to) {
		return priceHistoryRequest{}, errors.New("from must be on or before to")
	}
	return priceHistoryRequest{symbol: symbol, from: from, to: to, exchange: in.Exchange}, nil
}

type fundamentalsInput struct {
	Symbol   string `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter."`
}

type fundamentalsRequest struct {
	symbol   string
	exchange string
}

func (in fundamentalsInput) prepare() (fundamentalsRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return fundamentalsRequest{}, err
	}
	return fundamentalsRequest{symbol: symbol, exchange: in.Exchange}, nil
}

type optionsChainInput struct {
	Symbol     string   `json:"symbol" jsonschema:"Ticker symbol of the underlying security."`
	Expiry     string   `json:"expiry,omitempty" jsonschema:"Optional expiration date in YYYY-MM-DD format."`
	OptionType string   `json:"option_type,omitempty" jsonschema:"Optional contract type filter: 'call' or 'put'."`
	StrikeMin  *float64 `json:"strike_min,omitempty" jsonschema:"Optional minimum strike price."`
	StrikeMax  *float64 `json:"strike_max,omitempty" jsonschema:"Optional maximum strike price."`
}

type optionsChainRequest struct {
	symbol     string
	expiry     *time.Time
	optionType string
	strikeMin  *float64
	strikeMax  *float64
}

func (in optionsChainInput) prepare() (optionsChainRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return optionsChainRequest{}, err
	}
	optionType, err := validateOptionType(in.OptionType)
	if err != nil {
		return optionsChainRequest{}, err
	}
	var expiry *time.Time
	if strings.TrimSpace(in.Expiry) != "" {
		parsed, err := parseToolDate(in.Expiry, "expiry")
		if err != nil {
			return optionsChainRequest{}, err
		}
		expiry = &parsed
	}
	if in.StrikeMin != nil && in.StrikeMax != nil && *in.StrikeMin > *in.StrikeMax {
		return optionsChainRequest{}, errors.New("strike_min must be on or before strike_max")
	}
	return optionsChainRequest{
		symbol:     symbol,
		expiry:     expiry,
		optionType: optionType,
		strikeMin:  in.StrikeMin,
		strikeMax:  in.StrikeMax,
	}, nil
}

type statementInput struct {
	Symbol   string `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Period   string `json:"period,omitempty" jsonschema:"Optional reporting period: 'annual' (default) or 'quarter'."`
	Limit    int    `json:"limit,omitempty" jsonschema:"Optional maximum number of periods to return (1-20, default 5)."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter."`
}

type statementRequest struct {
	symbol   string
	period   string
	limit    int
	exchange string
}

func (in statementInput) prepare() (statementRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return statementRequest{}, err
	}
	period, err := normalizePeriod(in.Period)
	if err != nil {
		return statementRequest{}, err
	}
	return statementRequest{
		symbol:   symbol,
		period:   period,
		limit:    clampLimit(in.Limit),
		exchange: in.Exchange,
	}, nil
}

// statementEnvelope echoes the request scope alongside the decoded items.
type statementEnvelope struct {
	Statement string `json:"statement"`
	Symbol    string `json:"symbol"`
	Period    string `json:"period"`
	Limit     int    `json:"limit"`
	Exchange  string `json:"exchange,omitempty"`
	Items     any    `json:"items"`
}

type searchSymbolsInput struct {
	Query string `json:"q" jsonschema:"Free-text query matched against symbol and company names."`
}

type searchSymbolsRequest struct {
	query string
}

func (in searchSymbolsInput) prepare() (searchSymbolsRequest, error) {
	query, err := validateSearchQuery(in.Query)
	if err != nil {
		return searchSymbolsRequest{}, err
	}
	return searchSymbolsRequest{query: query}, nil
}

// --------------------------------------------------------------------------- //
// Validation helpers
// --------------------------------------------------------------------------- //

// requireSymbol trims and bounds a symbol. It is not uppercased here: the
// client normalizes it on the wire.
func requireSymbol(v string) (string, error) {
	symbol := strings.TrimSpace(v)
	if symbol == "" {
		return "", errors.New("symbol is required")
	}
	if len(symbol) > maxSymbolLength {
		return "", fmt.Errorf("symbol must be at most %d characters", maxSymbolLength)
	}
	return symbol, nil
}

// parseToolDate parses a YYYY-MM-DD date, naming the offending field.
func parseToolDate(v, field string) (time.Time, error) {
	parsed, err := time.Parse("2006-01-02", strings.TrimSpace(v))
	if err != nil {
		return time.Time{}, fmt.Errorf("%s must be a date in YYYY-MM-DD format", field)
	}
	return parsed, nil
}

// normalizePeriod defaults an absent period to "annual" and rejects anything
// outside the backend's accepted set.
func normalizePeriod(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "":
		return "annual", nil
	case "annual":
		return "annual", nil
	case "quarter":
		return "quarter", nil
	default:
		return "", errors.New("period must be 'annual' or 'quarter'")
	}
}

// clampLimit maps an absent or non-positive limit to the default and caps
// anything above the backend maximum.
func clampLimit(v int) int {
	if v <= 0 {
		return defaultStatementLimit
	}
	if v > maxStatementLimit {
		return maxStatementLimit
	}
	return v
}

// validateOptionType allows an absent filter or one of the two contract types.
func validateOptionType(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "":
		return "", nil
	case "call":
		return "call", nil
	case "put":
		return "put", nil
	default:
		return "", errors.New("option_type must be 'call' or 'put'")
	}
}

// validateSearchQuery trims and bounds the free-text query.
func validateSearchQuery(v string) (string, error) {
	query := strings.TrimSpace(v)
	if len(query) < minQueryLength || len(query) > maxQueryLength {
		return "", fmt.Errorf("q must be between %d and %d characters", minQueryLength, maxQueryLength)
	}
	return query, nil
}
