package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// dataPlanePath is the prefix of the backend service-to-service data plane
// (src/market/data_router.py). It is a stable contract: do not rename it.
const dataPlanePath = "/api/v1/market/data"

// BackendClient is a typed HTTP client for the market data plane. It sends the
// shared service token on every request and never touches a provider directly.
type BackendClient struct {
	group *RouteGroup
	cfg   Config
}

// NewBackendClient builds a client for the market data plane using cfg.
func NewBackendClient(cfg Config) (*BackendClient, error) {
	transport, err := NewTransport(cfg)
	if err != nil {
		return nil, err
	}
	group := transport.NewRouteGroup(dataPlanePath, cfg.ServiceToken)
	return &BackendClient{
		group: group,
		cfg:   cfg,
	}, nil
}

// MaxConcurrency returns the maximum number of concurrent outbound requests allowed.
func (c *BackendClient) MaxConcurrency() int {
	return c.group.transport.MaxConcurrency()
}

// Config returns the configuration used by this client.
func (c *BackendClient) Config() Config {
	return c.cfg
}

// Prices returns daily OHLC history for symbol.
//
// GET /api/v1/market/data/prices/{symbol}?from=&to=&interval=&exchange=
func (c *BackendClient) Prices(
	ctx context.Context,
	symbol string,
	from, to *time.Time,
	interval, exchange string,
) (json.RawMessage, error) {
	query := url.Values{}
	if from != nil {
		query.Set("from", from.Format("2006-01-02"))
	}
	if to != nil {
		query.Set("to", to.Format("2006-01-02"))
	}
	if interval != "" {
		query.Set("interval", interval)
	}
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out json.RawMessage
	if err := c.group.Get(ctx, "/prices/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Quote returns the live quote snapshot for symbol.
//
// GET /api/v1/market/data/quote/{symbol}?exchange=
func (c *BackendClient) Quote(
	ctx context.Context,
	symbol, exchange string,
) (json.RawMessage, error) {
	query := url.Values{}
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out json.RawMessage
	if err := c.group.Get(ctx, "/quote/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// SymbolSearch looks up symbols/companies by free-text query.
//
// GET /api/v1/market/data/symbols/search?q=
func (c *BackendClient) SymbolSearch(ctx context.Context, query string) (json.RawMessage, error) {
	values := url.Values{}
	values.Set("q", query)

	var out json.RawMessage
	if err := c.group.Get(ctx, "/symbols/search", values, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// OptionsChain returns the options chain for an underlying symbol.
//
// GET /api/v1/market/data/options/{symbol}?expiry=&option_type=&strike_min=&strike_max=
func (c *BackendClient) OptionsChain(
	ctx context.Context,
	symbol string,
	expiry time.Time,
	optionType string,
	strikeMin, strikeMax *float64,
) (json.RawMessage, error) {
	query := url.Values{}
	query.Set("expiry", expiry.Format("2006-01-02"))
	if optionType != "" {
		query.Set("option_type", optionType)
	}
	if strikeMin != nil {
		query.Set("strike_min", formatFloat(*strikeMin))
	}
	if strikeMax != nil {
		query.Set("strike_max", formatFloat(*strikeMax))
	}

	var out json.RawMessage
	if err := c.group.Get(ctx, "/options/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// OptionExpirations returns available option expiration dates for an underlying symbol.
//
// GET /api/v1/market/data/options/{symbol}/expirations
func (c *BackendClient) OptionExpirations(ctx context.Context, symbol string) (json.RawMessage, error) {
	var out json.RawMessage
	if err := c.group.Get(ctx, "/options/"+url.PathEscape(normalizeSymbol(symbol))+"/expirations", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Fundamentals returns the company profile plus key metrics and ratios.
//
// GET /api/v1/market/data/fundamentals/{symbol}?exchange=
func (c *BackendClient) Fundamentals(
	ctx context.Context,
	symbol, exchange string,
) (json.RawMessage, error) {
	query := url.Values{}
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out json.RawMessage
	if err := c.group.Get(ctx, "/fundamentals/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Statements returns the raw statement list for symbol.
//
// GET /api/v1/market/data/fundamentals/{symbol}/statements?statement=&period=&limit=&exchange=
//
// The backend response is returned as json.RawMessage and validated/decoded by
// decodeStatementList into a slice of raw JSON items.
func (c *BackendClient) Statements(
	ctx context.Context,
	symbol, statement, period string,
	limit int,
	exchange string,
) (json.RawMessage, error) {
	query := url.Values{}
	query.Set("statement", statement)
	if period != "" {
		query.Set("period", period)
	}
	if limit > 0 {
		query.Set("limit", fmt.Sprintf("%d", limit))
	}
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out json.RawMessage
	path := "/fundamentals/" + url.PathEscape(normalizeSymbol(symbol)) + "/statements"
	if err := c.group.Get(ctx, path, query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// normalizeSymbol upper-cases and trims a symbol before it is placed on the
// wire. T11 passes tool input through verbatim; normalization lives here.
func normalizeSymbol(symbol string) string {
	return strings.ToUpper(strings.TrimSpace(symbol))
}

// formatFloat renders a filter value without a trailing exponent and without
// unnecessary trailing zeros, matching the decimal query syntax the backend
// accepts.
func formatFloat(v float64) string {
	return strconv.FormatFloat(v, 'f', -1, 64)
}

// Statement literal values accepted by the backend statements route
// (data_router.market_data_statements). They are the only values ever placed on
// the wire.
const (
	statementIncome   = "income"
	statementBalance  = "balance"
	statementCashflow = "cashflow"
)

// decodeStatementList decodes the raw statements body for statement into a
// slice of raw JSON items.
//
// The backend statements route returns a bare list whose item type is a union
// (income / balance / cashflow); the body is fetched as json.RawMessage and
// decoded here. Each item must be a JSON object carrying the required non-empty
// date and symbol string headers. All line items and unknown fields pass
// through untouched.
//
// A decode failure is a plain error: the tool layer maps it onto the generic
// provider-failure result, so a cache-hit shape change is never reported as
// "no data".
func decodeStatementList(raw json.RawMessage, statement string) ([]json.RawMessage, error) {
	switch statement {
	case statementIncome, statementBalance, statementCashflow:
	default:
		return nil, fmt.Errorf("unknown statement type %q", statement)
	}

	var items []json.RawMessage
	if err := json.Unmarshal(raw, &items); err != nil {
		return nil, fmt.Errorf("decoding statement list: %w", err)
	}
	if items == nil {
		items = []json.RawMessage{}
	}

	for _, item := range items {
		var header struct {
			Date   *string `json:"date"`
			Symbol *string `json:"symbol"`
		}
		if err := json.Unmarshal(item, &header); err != nil {
			return nil, fmt.Errorf("decoding statement item header: %w", err)
		}
		if header.Date == nil || strings.TrimSpace(*header.Date) == "" ||
			header.Symbol == nil || strings.TrimSpace(*header.Symbol) == "" {
			return nil, errors.New("statement item is missing the date or symbol field")
		}
	}
	return items, nil
}
