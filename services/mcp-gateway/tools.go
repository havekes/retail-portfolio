package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"regexp"
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

	sectionProfile    = "profile"
	sectionKeyMetrics = "key_metrics"
	sectionRatios     = "ratios"
)

// noDataMessage is the successful result text used when the backend reports
// ErrNoData. A 404 can be a cached empty result within the cache TTL, so this
// is deliberately not phrased as an error or as "invalid symbol".
const noDataMessage = "No market data is available for this request."

const (
	descGetPriceHistory = `Historical daily, weekly, or monthly open/high/low/close price bars for a symbol over a date range.

Use when:
Analyzing historical price trends or charting OHLC bars. Defaults to 1 year of daily bars if dates are omitted. The response is capped at 2,000 bars; for long date ranges, narrow the window or choose a coarser interval ('week' or 'month').

Examples:
- "Daily price history for Apple in 2024" -> {"symbol": "AAPL", "from": "2024-01-01", "to": "2024-12-31", "interval": "day"}
- "Weekly bars for Tesla over 5 years" -> {"symbol": "TSLA", "interval": "week"}

Returns:
Top-level fields:
- symbol: ticker symbol.
- currency: listing currency code for all bar prices.
- from_date, to_date: covered date range in YYYY-MM-DD.
- interval: bar interval ('day', 'week', or 'month').
- items: array of OHLCV bar objects (date, open, high, low, close, volume). All price values are decimal strings denominated in currency.

See also:
get_quote, get_technical_indicator, resolve_symbol`

	descGetQuote = `Live quote snapshot for a ticker symbol, including price, daily change, trading volume, and timestamp.

Use when:
Checking the latest market price, intraday change, or trading volume for a security.

Examples:
- "Current price of Microsoft" -> {"symbol": "MSFT"}
- "Latest quote for Barclays on London exchange" -> {"symbol": "BARC", "exchange": "LSE"}

Returns:
Top-level fields:
- symbol: ticker symbol.
- price: latest price as a decimal string denominated in currency.
- change: absolute price change as a decimal string.
- change_percent: percentage change as a decimal string.
- volume: shares traded.
- timestamp: Unix epoch timestamp in seconds of the quote.
- currency: listing currency code (e.g. USD, CAD, GBP) for all monetary fields.

See also:
resolve_symbol, get_price_history, get_technical_indicator`

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

	descGetOptionsChain = `Option contracts chain for an underlying security on a specific expiration date, with optional strike and type filters.

Use when:
Pricing calls and puts, examining implied volatility, open interest, or bid/ask spreads. Use get_option_expirations first to obtain valid expiration dates.

Examples:
- "Calls for Tesla expiring 2026-01-16 with strikes 200 to 250" -> {"symbol": "TSLA", "expiry": "2026-01-16", "option_type": "call", "strike_min": 200, "strike_max": 250}
- "Full options chain for Apple on 2026-06-19" -> {"symbol": "AAPL", "expiry": "2026-06-19"}

Returns:
Top-level fields:
- symbol: underlying ticker symbol.
- expiry: contract expiration date in YYYY-MM-DD.
- underlying_price: current underlying price as a decimal string.
- currency: listing currency code for underlying and strikes.
- truncated: boolean indicating whether results reached the 250-contract cap. When truncated is true, narrow the chain by setting strike_min and strike_max or filtering option_type ('call' or 'put').
- items: array of option contract objects (strike, type, bid, ask, last, volume, open_interest). Strike and premium values are decimal strings denominated in currency.

See also:
get_option_expirations, get_quote, resolve_symbol`

	descGetOptionExpirations = `List of available option expiration dates for an underlying security, sorted in chronological order.

Use when:
Discovering valid expiration dates prior to querying get_options_chain, which requires an exact expiry date.

Examples:
- "Option expiration dates for Apple" -> {"symbol": "AAPL"}
- "Available expirations for SPY" -> {"symbol": "SPY"}

Returns:
Top-level fields:
- symbol: underlying ticker symbol.
- expirations: array of available expiration date strings in YYYY-MM-DD format, sorted ascending.

See also:
get_options_chain, get_quote, resolve_symbol`

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

	descResolveSymbol = `USE THIS FIRST to look up or verify the ticker symbol for a company or asset before calling price, fundamentals, or options tools. Resolves search queries to the best matching symbol and alternative candidates.

Use when:
Looking up an unknown ticker, verifying a company name, or disambiguating symbols across exchanges.

Examples:
- "Search Apple" -> {"query": "Apple"}
- "Find Royal Bank on Toronto exchange" -> {"query": "Royal Bank", "exchange": "TSX"}

Returns:
Top-level fields:
- best_match: object with symbol, exchange, name, and asset type for the closest match.
- alternatives: list of up to 10 additional candidate matches.

See also:
get_quote, get_price_history, get_fundamentals`

	descGetTechnicalIndicator = `Technical indicator series (SMA, EMA, RSI, MACD, Bollinger Bands) computed over daily price history for a symbol.

Use when:
Generating quantitative signals or momentum studies. Supported indicators: 'sma', 'ema', 'rsi', 'macd', 'bollinger'. Periods accept values between 2 and 400.

Examples:
- "20-day SMA for Apple in 2024" -> {"symbol": "AAPL", "indicator": "sma", "period": 20, "from": "2024-01-01", "to": "2024-12-31"}
- "RSI for Microsoft" -> {"symbol": "MSFT", "indicator": "rsi", "period": 14}

Returns:
Top-level fields:
- symbol: ticker symbol.
- indicator: indicator name ('sma', 'ema', 'rsi', 'macd', 'bollinger').
- currency: listing currency code for price-derived indicators.
- from_date, to_date: date range covered in YYYY-MM-DD.
- params: object echoing effective calculation parameters (e.g. period, fast, slow, signal, std_dev).
- points: array of calculated points with date and value fields. Values are decimal numbers.

See also:
get_price_history, get_quote, resolve_symbol`
)

// toolSpec packages metadata for an MCP tool registration.
type toolSpec struct {
	Name        string
	Title       string
	Description string
}

// registerTools attaches every market-data tool to server, closing over client.
func registerTools(server *mcp.Server, client *BackendClient, cfg Config) {
	addTool(server, toolSpec{
		Name:        "get_price_history",
		Title:       "Get Price History",
		Description: descGetPriceHistory,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in priceHistoryInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_price_history", cfg, in, priceHistoryInput.prepare, func(ctx context.Context, r priceHistoryRequest) (any, error) {
			return client.Prices(ctx, r.symbol, r.from, r.to, r.interval, r.exchange)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_quote",
		Title:       "Get Quote",
		Description: descGetQuote,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in quoteInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_quote", cfg, in, quoteInput.prepare, func(ctx context.Context, r quoteRequest) (any, error) {
			return client.Quote(ctx, r.symbol, r.exchange)
		})
	})

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
		Name:        "get_options_chain",
		Title:       "Get Options Chain",
		Description: descGetOptionsChain,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in optionsChainInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_options_chain", cfg, in, optionsChainInput.prepare, func(ctx context.Context, r optionsChainRequest) (any, error) {
			return client.OptionsChain(ctx, r.symbol, r.expiry, r.optionType, r.strikeMin, r.strikeMax)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_option_expirations",
		Title:       "Get Option Expirations",
		Description: descGetOptionExpirations,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in optionExpirationsInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_option_expirations", cfg, in, optionExpirationsInput.prepare, func(ctx context.Context, r optionExpirationsRequest) (any, error) {
			return client.OptionExpirations(ctx, r.symbol)
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

	addTool(server, toolSpec{
		Name:        "resolve_symbol",
		Title:       "Resolve Symbol",
		Description: descResolveSymbol,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in resolveSymbolInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "resolve_symbol", cfg, in, resolveSymbolInput.prepare, func(ctx context.Context, r resolveSymbolRequest) (any, error) {
			raw, err := client.SymbolSearch(ctx, r.query)
			if err != nil {
				return nil, err
			}
			var items []json.RawMessage
			if err := json.Unmarshal(raw, &items); err != nil {
				return nil, &backendError{class: ErrProvider, detail: err.Error()}
			}
			best, alts, err := rankSymbolMatches(items, r.query, r.exchange)
			if err != nil {
				return nil, err
			}
			return resolveSymbolResult{
				BestMatch:    best,
				Alternatives: alts,
			}, nil
		})
	})

	addTool(server, toolSpec{
		Name:        "get_technical_indicator",
		Title:       "Get Technical Indicator",
		Description: descGetTechnicalIndicator,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in technicalIndicatorInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_technical_indicator", cfg, in, technicalIndicatorInput.prepare, func(ctx context.Context, r technicalIndicatorRequest) (any, error) {
			return client.TechnicalIndicator(ctx, r.symbol, r.query)
		})
	})
}

// addTool is a thin wrapper over the SDK generic mcp.AddTool. Out is always any
// so the SDK never infers an output schema: results are plain JSON served as
// TextContent by the shared helpers below. It attaches ReadOnlyHint: true,
// IdempotentHint: true, and Title annotations to every registered tool.
func addTool[In any](
	server *mcp.Server,
	spec toolSpec,
	handler mcp.ToolHandlerFor[In, any],
) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        spec.Name,
		Title:       spec.Title,
		Description: spec.Description,
		Annotations: &mcp.ToolAnnotations{
			ReadOnlyHint:   true,
			IdempotentHint: true,
			Title:          spec.Title,
		},
	}, handler)
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

// runTool is the shared handler pipeline: it validates and normalizes the typed
// input via prepare, calls the backend, and maps the outcome to an MCP result
// per the T10 error contract.
func runTool[In, Req any](
	ctx context.Context,
	toolName string,
	cfg Config,
	in In,
	prepare func(In) (Req, error),
	doBackend func(context.Context, Req) (any, error),
) (*mcp.CallToolResult, any, error) {
	start := time.Now()
	if isDev(cfg.Environment) {
		slog.DebugContext(ctx, "tool invocation",
			slog.String("tool", toolName),
			slog.Any("arguments", in),
		)
	}

	req, err := prepare(in)
	if err != nil {
		slog.ErrorContext(ctx, "tool execution failed",
			slog.String("tool", toolName),
			slog.Any("arguments", in),
			slog.String("error_class", "ErrValidation"),
			slog.Int("status", http.StatusBadRequest),
			slog.String("detail", err.Error()),
		)
		return errorResult(err), nil, nil
	}

	payload, err := doBackend(ctx, req)
	duration := time.Since(start)

	if err != nil {
		if errors.Is(err, ErrNoData) {
			if isDev(cfg.Environment) {
				slog.DebugContext(ctx, "tool execution completed",
					slog.String("tool", toolName),
					slog.Duration("duration", duration),
					slog.String("response", noDataMessage),
				)
			}
			return noDataResult(), nil, nil
		}

		status := 0
		detail := err.Error()
		var backendErr *backendError
		if errors.As(err, &backendErr) {
			status = backendErr.Status()
			detail = backendErr.Detail()
		}

		var errorClass string
		switch {
		case errors.Is(err, ErrValidation):
			errorClass = "ErrValidation"
		case errors.Is(err, ErrConfiguration):
			errorClass = "ErrConfiguration"
		case errors.Is(err, ErrProvider):
			errorClass = "ErrProvider"
		default:
			errorClass = "ErrUnknown"
		}

		slog.ErrorContext(ctx, "tool execution failed",
			slog.String("tool", toolName),
			slog.Any("arguments", in),
			slog.String("error_class", errorClass),
			slog.Int("status", status),
			slog.String("detail", detail),
		)
		return mapBackendError(err), nil, nil
	}

	res, out, retErr := successResult(payload)
	if isDev(cfg.Environment) && res != nil && len(res.Content) > 0 {
		var responseText string
		if tc, ok := res.Content[0].(*mcp.TextContent); ok {
			responseText = tc.Text
		}
		slog.DebugContext(ctx, "tool execution completed",
			slog.String("tool", toolName),
			slog.Duration("duration", duration),
			slog.String("response", responseText),
		)
	}
	return res, out, retErr
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
	From     string `json:"from,omitempty" jsonschema:"Optional start date (inclusive) in YYYY-MM-DD format."`
	To       string `json:"to,omitempty" jsonschema:"Optional end date (inclusive) in YYYY-MM-DD format."`
	Interval string `json:"interval,omitempty" jsonschema:"Optional bar interval: 'day' (default), 'week', or 'month'."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type priceHistoryRequest struct {
	symbol   string
	from     *time.Time
	to       *time.Time
	interval string
	exchange string
}

func (in priceHistoryInput) prepare() (priceHistoryRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return priceHistoryRequest{}, err
	}
	var fromPtr, toPtr *time.Time
	if strings.TrimSpace(in.From) != "" {
		from, err := parseToolDate(in.From, "from")
		if err != nil {
			return priceHistoryRequest{}, err
		}
		fromPtr = &from
	}
	if strings.TrimSpace(in.To) != "" {
		to, err := parseToolDate(in.To, "to")
		if err != nil {
			return priceHistoryRequest{}, err
		}
		toPtr = &to
	}
	if fromPtr != nil && toPtr != nil && fromPtr.After(*toPtr) {
		return priceHistoryRequest{}, errors.New("from must be on or before to")
	}
	interval, err := normalizeInterval(in.Interval)
	if err != nil {
		return priceHistoryRequest{}, err
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return priceHistoryRequest{}, err
	}
	return priceHistoryRequest{
		symbol:   symbol,
		from:     fromPtr,
		to:       toPtr,
		interval: interval,
		exchange: exchange,
	}, nil
}

type quoteInput struct {
	Symbol   string `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type quoteRequest struct {
	symbol   string
	exchange string
}

func (in quoteInput) prepare() (quoteRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return quoteRequest{}, err
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return quoteRequest{}, err
	}
	return quoteRequest{
		symbol:   symbol,
		exchange: exchange,
	}, nil
}

type technicalIndicatorInput struct {
	Symbol    string   `json:"symbol" jsonschema:"Ticker symbol of the security."`
	Indicator string   `json:"indicator" jsonschema:"Indicator type: 'sma', 'ema', 'rsi', 'macd', or 'bollinger'."`
	Period    *int     `json:"period,omitempty" jsonschema:"Optional period for SMA, EMA, RSI (default 14), or Bollinger Bands (default 20). Range: 2 to 400."`
	Fast      *int     `json:"fast,omitempty" jsonschema:"Optional fast period for MACD (default 12). Range: 2 to 400."`
	Slow      *int     `json:"slow,omitempty" jsonschema:"Optional slow period for MACD (default 26). Range: 2 to 400."`
	Signal    *int     `json:"signal,omitempty" jsonschema:"Optional signal period for MACD (default 9). Range: 2 to 400."`
	StdDev    *float64 `json:"std_dev,omitempty" jsonschema:"Optional standard deviation multiplier for Bollinger Bands (default 2.0)."`
	From      string   `json:"from,omitempty" jsonschema:"Optional start date (inclusive) in YYYY-MM-DD format."`
	To        string   `json:"to,omitempty" jsonschema:"Optional end date (inclusive) in YYYY-MM-DD format."`
	Exchange  string   `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type technicalIndicatorRequest struct {
	symbol string
	query  indicatorQuery
}

func (in technicalIndicatorInput) prepare() (technicalIndicatorRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return technicalIndicatorRequest{}, err
	}
	indicator, err := validateIndicator(in.Indicator)
	if err != nil {
		return technicalIndicatorRequest{}, err
	}
	if err := validatePeriodParam("period", in.Period); err != nil {
		return technicalIndicatorRequest{}, err
	}
	if err := validatePeriodParam("fast", in.Fast); err != nil {
		return technicalIndicatorRequest{}, err
	}
	if err := validatePeriodParam("slow", in.Slow); err != nil {
		return technicalIndicatorRequest{}, err
	}
	if err := validatePeriodParam("signal", in.Signal); err != nil {
		return technicalIndicatorRequest{}, err
	}
	if in.StdDev != nil && *in.StdDev <= 0 {
		return technicalIndicatorRequest{}, errors.New("std_dev must be greater than 0")
	}
	var fromPtr, toPtr *time.Time
	if strings.TrimSpace(in.From) != "" {
		from, err := parseToolDate(in.From, "from")
		if err != nil {
			return technicalIndicatorRequest{}, err
		}
		fromPtr = &from
	}
	if strings.TrimSpace(in.To) != "" {
		to, err := parseToolDate(in.To, "to")
		if err != nil {
			return technicalIndicatorRequest{}, err
		}
		toPtr = &to
	}
	if fromPtr != nil && toPtr != nil && fromPtr.After(*toPtr) {
		return technicalIndicatorRequest{}, errors.New("from must be on or before to")
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return technicalIndicatorRequest{}, err
	}
	return technicalIndicatorRequest{
		symbol: symbol,
		query: indicatorQuery{
			indicator: indicator,
			period:    in.Period,
			fast:      in.Fast,
			slow:      in.Slow,
			signal:    in.Signal,
			stdDev:    in.StdDev,
			from:      fromPtr,
			to:        toPtr,
			exchange:  exchange,
		},
	}, nil
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

type optionsChainInput struct {
	Symbol     string   `json:"symbol" jsonschema:"Ticker symbol of the underlying security."`
	Expiry     string   `json:"expiry" jsonschema:"Expiration date in YYYY-MM-DD format (use get_option_expirations to list available dates)."`
	OptionType string   `json:"option_type,omitempty" jsonschema:"Optional contract type filter: 'call' or 'put'."`
	StrikeMin  *float64 `json:"strike_min,omitempty" jsonschema:"Optional minimum strike price."`
	StrikeMax  *float64 `json:"strike_max,omitempty" jsonschema:"Optional maximum strike price."`
}

type optionsChainRequest struct {
	symbol     string
	expiry     time.Time
	optionType string
	strikeMin  *float64
	strikeMax  *float64
}

func (in optionsChainInput) prepare() (optionsChainRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return optionsChainRequest{}, err
	}
	if strings.TrimSpace(in.Expiry) == "" {
		return optionsChainRequest{}, errors.New("expiry is required; use get_option_expirations to list available dates")
	}
	expiry, err := parseToolDate(in.Expiry, "expiry")
	if err != nil {
		return optionsChainRequest{}, err
	}
	optionType, err := validateOptionType(in.OptionType)
	if err != nil {
		return optionsChainRequest{}, err
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

type optionExpirationsInput struct {
	Symbol string `json:"symbol" jsonschema:"Ticker symbol of the underlying security."`
}

type optionExpirationsRequest struct {
	symbol string
}

func (in optionExpirationsInput) prepare() (optionExpirationsRequest, error) {
	symbol, err := requireSymbol(in.Symbol)
	if err != nil {
		return optionExpirationsRequest{}, err
	}
	return optionExpirationsRequest{symbol: symbol}, nil
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

type resolveSymbolInput struct {
	Query    string `json:"query" jsonschema:"Company name or ticker query to resolve."`
	Exchange string `json:"exchange,omitempty" jsonschema:"Optional exchange filter (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE)."`
}

type resolveSymbolRequest struct {
	query    string
	exchange string
}

func (in resolveSymbolInput) prepare() (resolveSymbolRequest, error) {
	query, err := validateSearchQuery(in.Query)
	if err != nil {
		return resolveSymbolRequest{}, err
	}
	exchange, err := validateExchange(in.Exchange)
	if err != nil {
		return resolveSymbolRequest{}, err
	}
	return resolveSymbolRequest{
		query:    query,
		exchange: exchange,
	}, nil
}

type resolveSymbolResult struct {
	BestMatch    json.RawMessage   `json:"best_match"`
	Alternatives []json.RawMessage `json:"alternatives"`
}

type symbolMatchSummary struct {
	Symbol            string `json:"symbol"`
	ExchangeShortName string `json:"exchange_short_name"`
	AltExchangeShort  string `json:"exchangeShortName"`
}

func (s symbolMatchSummary) exchangeShort() string {
	if s.ExchangeShortName != "" {
		return s.ExchangeShortName
	}
	return s.AltExchangeShort
}

const maxAlternatives = 10

// rankSymbolMatches ranks symbol candidates against the query and optional preferred exchange.
// Ranking tiers:
//  1. case-insensitive exact symbol match on the preferred exchange
//  2. exact symbol match anywhere
//  3. first result on the preferred exchange
//  4. first result
//
// Alternatives are the remaining results in backend order, capped at 10.
func rankSymbolMatches(items []json.RawMessage, query, exchange string) (json.RawMessage, []json.RawMessage, error) {
	if len(items) == 0 {
		return nil, nil, &backendError{class: ErrNoData}
	}

	cleanQuery := strings.TrimSpace(query)
	cleanExchange := strings.TrimSpace(exchange)

	summaries := make([]symbolMatchSummary, len(items))
	for i, item := range items {
		if err := json.Unmarshal(item, &summaries[i]); err != nil {
			return nil, nil, &backendError{class: ErrProvider, detail: err.Error()}
		}
	}

	bestIdx := -1

	// Tier 1: exact symbol match on the preferred exchange.
	if cleanExchange != "" {
		for i, s := range summaries {
			if strings.EqualFold(s.Symbol, cleanQuery) && strings.EqualFold(s.exchangeShort(), cleanExchange) {
				bestIdx = i
				break
			}
		}
	}

	// Tier 2: exact symbol match anywhere.
	if bestIdx == -1 {
		for i, s := range summaries {
			if strings.EqualFold(s.Symbol, cleanQuery) {
				bestIdx = i
				break
			}
		}
	}

	// Tier 3: first result on the preferred exchange.
	if bestIdx == -1 && cleanExchange != "" {
		for i, s := range summaries {
			if strings.EqualFold(s.exchangeShort(), cleanExchange) {
				bestIdx = i
				break
			}
		}
	}

	// Tier 4: first result.
	if bestIdx == -1 {
		bestIdx = 0
	}

	best := items[bestIdx]

	alts := make([]json.RawMessage, 0, min(len(items)-1, maxAlternatives))
	for i, item := range items {
		if i == bestIdx {
			continue
		}
		alts = append(alts, item)
		if len(alts) == maxAlternatives {
			break
		}
	}

	return best, alts, nil
}

// --------------------------------------------------------------------------- //
// Validation helpers
// --------------------------------------------------------------------------- //

// symbolPattern enforces the allowed ticker charset and bounds: optional leading
// '^', leading alphanumeric character, followed by up to 30 alphanumeric, '.',
// '-', or '=' characters (max 32 chars).
var symbolPattern = regexp.MustCompile(`^\^?[A-Za-z0-9][A-Za-z0-9.\-=]{0,30}$`)

// requireSymbol bounds and validates a symbol against symbolPattern. It is not
// uppercased here: the client normalizes it on the wire.
func requireSymbol(v string) (string, error) {
	if strings.TrimSpace(v) == "" {
		return "", errors.New("symbol is required")
	}
	if len(v) > maxSymbolLength {
		return "", fmt.Errorf("symbol must be at most %d characters", maxSymbolLength)
	}
	if !symbolPattern.MatchString(v) {
		return "", fmt.Errorf("invalid symbol %q", v)
	}
	return v, nil
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

// normalizeInterval validates the optional interval enum. An absent value
// returns "" (allowing backend default to apply).
func normalizeInterval(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "":
		return "", nil
	case "day":
		return "day", nil
	case "week":
		return "week", nil
	case "month":
		return "month", nil
	default:
		return "", errors.New("interval must be 'day', 'week', or 'month'")
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
		return "", fmt.Errorf("query must be between %d and %d characters", minQueryLength, maxQueryLength)
	}
	return query, nil
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

// supportedExchanges lists the canonical exchange codes accepted by the
// backend data plane and mapped to provider suffixes.
var supportedExchanges = []string{"NYSE", "NASDAQ", "NYSEARCA", "AMEX", "TSX", "LSE"}

// validateExchange normalizes an optional exchange filter by trimming and
// uppercasing it. An empty string passes through as "". If provided, it must
// match one of the canonical supportedExchanges.
func validateExchange(v string) (string, error) {
	clean := strings.ToUpper(strings.TrimSpace(v))
	if clean == "" {
		return "", nil
	}
	for _, code := range supportedExchanges {
		if clean == code {
			return clean, nil
		}
	}
	return "", fmt.Errorf("exchange must be one of: %s", strings.Join(supportedExchanges, ", "))
}

// validateIndicator validates the indicator enum.
func validateIndicator(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "sma":
		return "sma", nil
	case "ema":
		return "ema", nil
	case "rsi":
		return "rsi", nil
	case "macd":
		return "macd", nil
	case "bollinger":
		return "bollinger", nil
	default:
		return "", errors.New("indicator must be 'sma', 'ema', 'rsi', 'macd', or 'bollinger'")
	}
}

// validatePeriodParam checks that an optional period parameter is within [2, 400].
func validatePeriodParam(name string, p *int) error {
	if p != nil && (*p < 2 || *p > 400) {
		return fmt.Errorf("%s must be between 2 and 400", name)
	}
	return nil
}
