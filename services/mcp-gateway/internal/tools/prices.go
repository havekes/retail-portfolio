package tools

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

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

// registerPriceTools attaches price and technical indicator tools to server.
func registerPriceTools(server *mcp.Server, client *backend.MarketClient) {
	addTool(server, toolSpec{
		Name:        "get_price_history",
		Title:       "Get Price History",
		Description: descGetPriceHistory,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in priceHistoryInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_price_history", in, priceHistoryInput.prepare, func(ctx context.Context, r priceHistoryRequest) (any, error) {
			return client.Prices(ctx, r.symbol, r.from, r.to, r.interval, r.exchange)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_quote",
		Title:       "Get Quote",
		Description: descGetQuote,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in quoteInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_quote", in, quoteInput.prepare, func(ctx context.Context, r quoteRequest) (any, error) {
			return client.Quote(ctx, r.symbol, r.exchange)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_technical_indicator",
		Title:       "Get Technical Indicator",
		Description: descGetTechnicalIndicator,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in technicalIndicatorInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_technical_indicator", in, technicalIndicatorInput.prepare, func(ctx context.Context, r technicalIndicatorRequest) (any, error) {
			return client.TechnicalIndicator(ctx, r.symbol, r.query)
		})
	})
}

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
	query  backend.IndicatorQuery
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
		query: backend.IndicatorQuery{
			Indicator: indicator,
			Period:    in.Period,
			Fast:      in.Fast,
			Slow:      in.Slow,
			Signal:    in.Signal,
			StdDev:    in.StdDev,
			From:      fromPtr,
			To:        toPtr,
			Exchange:  exchange,
		},
	}, nil
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
