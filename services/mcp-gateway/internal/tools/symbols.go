package tools

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

const descResolveSymbol = `USE THIS FIRST to look up or verify the ticker symbol for a company or asset before calling price, fundamentals, or options tools. Resolves search queries to the best matching symbol and alternative candidates.

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

// registerSymbolTools attaches symbol resolution tools to server.
func registerSymbolTools(server *mcp.Server, client *backend.MarketClient) {
	addTool(server, toolSpec{
		Name:        "resolve_symbol",
		Title:       "Resolve Symbol",
		Description: descResolveSymbol,
	}, func(ctx context.Context, _ *mcp.CallToolRequest, in resolveSymbolInput) (*mcp.CallToolResult, any, error) {
		return runTool(ctx, "resolve_symbol", in, resolveSymbolInput.prepare, func(ctx context.Context, r resolveSymbolRequest) (any, error) {
			raw, err := client.SymbolSearch(ctx, r.query)
			if err != nil {
				return nil, err
			}
			var items []json.RawMessage
			if err := json.Unmarshal(raw, &items); err != nil {
				return nil, backend.NewError(backend.ErrProvider, err.Error())
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
		return nil, nil, backend.NewError(backend.ErrNoData, "")
	}

	cleanQuery := strings.TrimSpace(query)
	cleanExchange := strings.TrimSpace(exchange)

	summaries := make([]symbolMatchSummary, len(items))
	for i, item := range items {
		if err := json.Unmarshal(item, &summaries[i]); err != nil {
			return nil, nil, backend.NewError(backend.ErrProvider, err.Error())
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
