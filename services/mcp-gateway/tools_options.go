package main

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

const (
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
)

// registerOptionsTools attaches option chain and expiration tools to server.
func registerOptionsTools(server *mcp.Server, client *backend.MarketClient) {
	addTool(server, toolSpec{
		Name:        "get_options_chain",
		Title:       "Get Options Chain",
		Description: descGetOptionsChain,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in optionsChainInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_options_chain", in, optionsChainInput.prepare, func(ctx context.Context, r optionsChainRequest) (any, error) {
			return client.OptionsChain(ctx, r.symbol, r.expiry, r.optionType, r.strikeMin, r.strikeMax)
		})
	})

	addTool(server, toolSpec{
		Name:        "get_option_expirations",
		Title:       "Get Option Expirations",
		Description: descGetOptionExpirations,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in optionExpirationsInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "get_option_expirations", in, optionExpirationsInput.prepare, func(ctx context.Context, r optionExpirationsRequest) (any, error) {
			return client.OptionExpirations(ctx, r.symbol)
		})
	})
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
