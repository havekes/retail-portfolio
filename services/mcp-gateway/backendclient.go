package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// dataPlanePath is the prefix of the backend service-to-service data plane
// (src/market/data_router.py). It is a stable contract: do not rename it.
const dataPlanePath = "/api/v1/market/data"

// serviceTokenHeader is the shared-secret header expected by the backend
// (src/auth/api.py).
const serviceTokenHeader = "X-Service-Token" //nolint:gosec // header name, not a secret

// defaultHTTPTimeout bounds every backend call so a stalled data plane cannot
// pin a tool call open forever.
const defaultHTTPTimeout = 15 * time.Second

// maxResponseBytes caps how much of a backend response body is buffered.
const maxResponseBytes = 8 << 20 // 8 MiB

// errorDetailLimit caps the diagnostic detail retained on a backendError.
const errorDetailLimit = 512

// Error taxonomy for backend failures. These sentinels are the contract T11's
// tools map onto MCP results:
//
//   - ErrNoData: the backend has no data for the request right now. This is a
//     normal outcome (404 may be a cached empty result within the TTL) and must
//     never be presented as "invalid symbol".
//   - ErrConfiguration: the service token was rejected. This is an operator
//     problem, not a user one.
//   - ErrProvider: the market data provider is unreachable or misbehaving.
//
// The sentinel messages are deliberately generic: they contain neither the
// service token nor any provider name, so they are safe to surface to an agent.
var (
	ErrNoData        = errors.New("no market data found")
	ErrConfiguration = errors.New("market data authentication failed — check service token configuration")
	ErrProvider      = errors.New("market data is temporarily unavailable")
)

// backendError classifies a backend failure while keeping Error() generic.
//
// The underlying detail (status code and a truncated response body) is retained
// for Go-side diagnostics only; it is intentionally excluded from Error() so a
// tool handler that forwards err.Error() cannot leak internals to an agent.
type backendError struct {
	class  error
	status int
	detail string
}

func (e *backendError) Error() string { return e.class.Error() }

// Unwrap exposes the sentinel so errors.Is(err, ErrNoData) &c. keep working.
func (e *backendError) Unwrap() error { return e.class }

// Status returns the HTTP status that produced the error, or 0 for transport
// and decoding failures.
func (e *backendError) Status() int { return e.status }

// Detail returns the Go-side diagnostic detail. It must not be forwarded to
// agent-facing output.
func (e *backendError) Detail() string { return e.detail }

// classifyBackendError maps a non-2xx backend response onto the error taxonomy.
//
// 404 and 422 both mean "no data for this request"; 401/403 mean the service
// token was rejected; every other status (including 5xx and unexpected 4xx) is
// treated as a provider-side failure so callers always get one of three classes.
func classifyBackendError(status int, body []byte) error {
	detail := truncateDetail(string(body))
	switch status {
	case http.StatusNotFound, http.StatusUnprocessableEntity:
		return &backendError{class: ErrNoData, status: status, detail: detail}
	case http.StatusUnauthorized, http.StatusForbidden:
		return &backendError{class: ErrConfiguration, status: status, detail: detail}
	default:
		return &backendError{class: ErrProvider, status: status, detail: detail}
	}
}

func truncateDetail(s string) string {
	if len(s) > errorDetailLimit {
		return s[:errorDetailLimit]
	}
	return s
}

// BackendClient is a typed HTTP client for the backend data plane. It sends the
// shared service token on every request and never touches a provider directly.
type BackendClient struct {
	baseURL    *url.URL
	token      string
	httpClient *http.Client
}

// NewBackendClient validates baseURL and builds a client. baseURL must be an
// absolute http(s) origin; a trailing slash is tolerated.
func NewBackendClient(baseURL, token string) (*BackendClient, error) {
	trimmed := strings.TrimRight(strings.TrimSpace(baseURL), "/")
	if trimmed == "" {
		return nil, errors.New("backend base URL is required")
	}
	parsed, err := url.Parse(trimmed)
	if err != nil {
		return nil, fmt.Errorf("backend base URL is not a valid URL: %w", err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, errors.New("backend base URL must use http or https")
	}
	if parsed.Host == "" {
		return nil, errors.New("backend base URL must include a host")
	}

	return &BackendClient{
		baseURL:    parsed,
		token:      token,
		httpClient: &http.Client{Timeout: defaultHTTPTimeout},
	}, nil
}

// Prices returns daily OHLC history for symbol.
//
// GET /api/v1/market/data/prices/{symbol}?from=&to=&exchange=
func (c *BackendClient) Prices(
	ctx context.Context,
	symbol string,
	from, to time.Time,
	exchange string,
) (PriceHistory, error) {
	query := url.Values{}
	query.Set("from", from.Format("2006-01-02"))
	query.Set("to", to.Format("2006-01-02"))
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out PriceHistory
	if err := c.get(ctx, "/prices/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return PriceHistory{}, err
	}
	return out, nil
}

// SymbolSearch looks up symbols/companies by free-text query.
//
// GET /api/v1/market/data/symbols/search?q=
func (c *BackendClient) SymbolSearch(ctx context.Context, query string) ([]SymbolLookupResult, error) {
	values := url.Values{}
	values.Set("q", query)

	var out []SymbolLookupResult
	if err := c.get(ctx, "/symbols/search", values, &out); err != nil {
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
	expiry *time.Time,
	optionType string,
	strikeMin, strikeMax *float64,
) (OptionsChain, error) {
	query := url.Values{}
	if expiry != nil {
		query.Set("expiry", expiry.Format("2006-01-02"))
	}
	if optionType != "" {
		query.Set("option_type", optionType)
	}
	if strikeMin != nil {
		query.Set("strike_min", formatFloat(*strikeMin))
	}
	if strikeMax != nil {
		query.Set("strike_max", formatFloat(*strikeMax))
	}

	var out OptionsChain
	if err := c.get(ctx, "/options/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return OptionsChain{}, err
	}
	return out, nil
}

// Fundamentals returns the company profile plus key metrics and ratios.
//
// GET /api/v1/market/data/fundamentals/{symbol}?exchange=
func (c *BackendClient) Fundamentals(
	ctx context.Context,
	symbol, exchange string,
) (CompanyFundamentals, error) {
	query := url.Values{}
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out CompanyFundamentals
	if err := c.get(ctx, "/fundamentals/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return CompanyFundamentals{}, err
	}
	return out, nil
}

// Statements returns the raw statement list for symbol.
//
// GET /api/v1/market/data/fundamentals/{symbol}/statements?statement=&period=&limit=&exchange=
//
// The backend response type depends on statement (income / balance / cashflow),
// so the body is returned as json.RawMessage for T11 to decode per statement.
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
	if err := c.get(ctx, path, query, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// get performs a GET against the data plane and decodes a 2xx JSON body into
// out. Every failure is normalized to one of the ErrNoData / ErrConfiguration /
// ErrProvider classes.
func (c *BackendClient) get(ctx context.Context, path string, query url.Values, out any) error {
	endpoint, err := url.Parse(c.baseURL.String() + dataPlanePath + path)
	if err != nil {
		return &backendError{class: ErrProvider, detail: err.Error()}
	}
	endpoint.RawQuery = query.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return &backendError{class: ErrProvider, detail: err.Error()}
	}
	req.Header.Set(serviceTokenHeader, c.token)
	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return &backendError{class: ErrProvider, detail: err.Error()}
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		return &backendError{class: ErrProvider, status: resp.StatusCode, detail: err.Error()}
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return classifyBackendError(resp.StatusCode, body)
	}

	if err := json.Unmarshal(body, out); err != nil {
		return &backendError{
			class:  ErrProvider,
			status: resp.StatusCode,
			detail: "malformed response from the market data service",
		}
	}
	return nil
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

// --------------------------------------------------------------------------- //
// Data-plane response types
//
// These mirror the backend Pydantic models in src/market/schema.py and
// src/market/api_types.py field-for-field. FastAPI serializes with the declared
// (snake_case) field names — the models set no aliases — and Pydantic v2 emits
// ``Decimal`` as a JSON *string* while integers stay JSON numbers. The Decimal
// type below accepts either so the structs decode the real backend output.
// Dates are ISO-8601 ``YYYY-MM-DD`` strings.
// --------------------------------------------------------------------------- //

// Decimal is a decimal value that round-trips as a JSON string (the shape
// Pydantic v2 emits for “Decimal“) while also accepting a bare JSON number.
type Decimal string

// UnmarshalJSON accepts a JSON string, number, or null.
func (d *Decimal) UnmarshalJSON(data []byte) error {
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "" || trimmed == "null" {
		*d = ""
		return nil
	}
	if trimmed[0] == '"' {
		var s string
		if err := json.Unmarshal(data, &s); err != nil {
			return err
		}
		*d = Decimal(s)
		return nil
	}
	*d = Decimal(trimmed)
	return nil
}

// MarshalJSON emits a JSON string, preserving the backend's representation.
func (d Decimal) MarshalJSON() ([]byte, error) {
	return json.Marshal(string(d))
}

// PriceBar is one daily OHLC bar (schema.PriceBar).
type PriceBar struct {
	Date          string   `json:"date"`
	Open          Decimal  `json:"open"`
	High          Decimal  `json:"high"`
	Low           Decimal  `json:"low"`
	Close         Decimal  `json:"close"`
	Volume        int64    `json:"volume"`
	AdjustedClose *Decimal `json:"adjusted_close,omitempty"`
}

// PriceHistory is the unified daily price-history response
// (schema.PriceHistoryResponse).
type PriceHistory struct {
	Symbol   string     `json:"symbol"`
	Exchange *string    `json:"exchange,omitempty"`
	FromDate string     `json:"from_date"`
	ToDate   string     `json:"to_date"`
	Items    []PriceBar `json:"items"`
}

// SymbolLookupResult is one symbol-search hit (api_types.SymbolLookupResult).
type SymbolLookupResult struct {
	Symbol            string  `json:"symbol"`
	Name              string  `json:"name"`
	Exchange          *string `json:"exchange,omitempty"`
	ExchangeShortName *string `json:"exchange_short_name,omitempty"`
	Currency          *string `json:"currency,omitempty"`
	SecurityType      *string `json:"security_type,omitempty"`
	Country           *string `json:"country,omitempty"`
}

// CompanyProfile is the company-details object (api_types.CompanyProfile).
type CompanyProfile struct {
	Symbol            string   `json:"symbol"`
	CompanyName       string   `json:"company_name"`
	MarketCap         *Decimal `json:"market_cap,omitempty"`
	Sector            *string  `json:"sector,omitempty"`
	Industry          *string  `json:"industry,omitempty"`
	Beta              *Decimal `json:"beta,omitempty"`
	Price             *Decimal `json:"price,omitempty"`
	Website           *string  `json:"website,omitempty"`
	Description       *string  `json:"description,omitempty"`
	CEO               *string  `json:"ceo,omitempty"`
	FullTimeEmployees *int64   `json:"full_time_employees,omitempty"`
	ExchangeShortName *string  `json:"exchange_short_name,omitempty"`
	Exchange          *string  `json:"exchange,omitempty"`
	Currency          *string  `json:"currency,omitempty"`
	IPODate           *string  `json:"ipo_date,omitempty"`
	CIK               *string  `json:"cik,omitempty"`
	ISIN              *string  `json:"isin,omitempty"`
	Image             *string  `json:"image,omitempty"`
	IsActivelyTrading *bool    `json:"is_actively_trading,omitempty"`
}

// KeyMetrics is the valuation-snapshot object (api_types.KeyMetrics).
type KeyMetrics struct {
	Symbol                    string   `json:"symbol"`
	Date                      string   `json:"date"`
	FiscalYear                *string  `json:"fiscal_year,omitempty"`
	Period                    *string  `json:"period,omitempty"`
	MarketCap                 *Decimal `json:"market_cap,omitempty"`
	EnterpriseValue           *Decimal `json:"enterprise_value,omitempty"`
	PERatio                   *Decimal `json:"pe_ratio,omitempty"`
	PEGRatio                  *Decimal `json:"peg_ratio,omitempty"`
	PriceToSalesRatio         *Decimal `json:"price_to_sales_ratio,omitempty"`
	PriceToBookRatio          *Decimal `json:"price_to_book_ratio,omitempty"`
	EnterpriseValueOverEBITDA *Decimal `json:"enterprise_value_over_ebitda,omitempty"`
	EVToSales                 *Decimal `json:"ev_to_sales,omitempty"`
	DividendYield             *Decimal `json:"dividend_yield,omitempty"`
	PayoutRatio               *Decimal `json:"payout_ratio,omitempty"`
	CurrentRatio              *Decimal `json:"current_ratio,omitempty"`
	QuickRatio                *Decimal `json:"quick_ratio,omitempty"`
	DebtToEquity              *Decimal `json:"debt_to_equity,omitempty"`
	WorkingCapital            *Decimal `json:"working_capital,omitempty"`
}

// FinancialRatios is the ratios object (api_types.FinancialRatios).
type FinancialRatios struct {
	Symbol                  string   `json:"symbol"`
	Date                    string   `json:"date"`
	FiscalYear              *string  `json:"fiscal_year,omitempty"`
	Period                  *string  `json:"period,omitempty"`
	GrossProfitMargin       *Decimal `json:"gross_profit_margin,omitempty"`
	OperatingProfitMargin   *Decimal `json:"operating_profit_margin,omitempty"`
	NetProfitMargin         *Decimal `json:"net_profit_margin,omitempty"`
	ReturnOnAssets          *Decimal `json:"return_on_assets,omitempty"`
	ReturnOnEquity          *Decimal `json:"return_on_equity,omitempty"`
	ReturnOnCapitalEmployed *Decimal `json:"return_on_capital_employed,omitempty"`
	InterestCoverage        *Decimal `json:"interest_coverage,omitempty"`
	QuickRatio              *Decimal `json:"quick_ratio,omitempty"`
	CurrentRatio            *Decimal `json:"current_ratio,omitempty"`
	DebtToEquity            *Decimal `json:"debt_to_equity,omitempty"`
	PriceEarningsRatio      *Decimal `json:"price_earnings_ratio,omitempty"`
	BookValuePerShare       *Decimal `json:"book_value_per_share,omitempty"`
	DividendYield           *Decimal `json:"dividend_yield,omitempty"`
}

// CompanyFundamentals is the fundamentals overview aggregate
// (api_types.CompanyFundamentals).
type CompanyFundamentals struct {
	Profile    CompanyProfile  `json:"profile"`
	KeyMetrics KeyMetrics      `json:"key_metrics"`
	Ratios     FinancialRatios `json:"ratios"`
}

// OptionsContract is an options contract reference (api_types.OptionsContract).
type OptionsContract struct {
	ContractTicker    string  `json:"contract_ticker"`
	Symbol            string  `json:"symbol"`
	StrikePrice       Decimal `json:"strike_price"`
	ExpirationDate    string  `json:"expiration_date"`
	ContractType      string  `json:"contract_type"`
	SharesPerContract int64   `json:"shares_per_contract"`
	PrimaryExchange   *string `json:"primary_exchange,omitempty"`
	Active            bool    `json:"active"`
}

// OptionsGreeks is the greeks object (api_types.OptionsGreeks).
type OptionsGreeks struct {
	Delta *Decimal `json:"delta,omitempty"`
	Gamma *Decimal `json:"gamma,omitempty"`
	Theta *Decimal `json:"theta,omitempty"`
	Vega  *Decimal `json:"vega,omitempty"`
	Rho   *Decimal `json:"rho,omitempty"`
}

// OptionsQuote is the per-contract snapshot (api_types.OptionsQuote).
type OptionsQuote struct {
	ImpliedVolatility *Decimal       `json:"implied_volatility,omitempty"`
	OpenInterest      *Decimal       `json:"open_interest,omitempty"`
	DayVolume         *int64         `json:"day_volume,omitempty"`
	DayOpen           *Decimal       `json:"day_open,omitempty"`
	DayHigh           *Decimal       `json:"day_high,omitempty"`
	DayLow            *Decimal       `json:"day_low,omitempty"`
	DayClose          *Decimal       `json:"day_close,omitempty"`
	Greeks            *OptionsGreeks `json:"greeks,omitempty"`
}

// OptionsChainEntry pairs a contract with its snapshot (api_types.OptionsChainEntry).
type OptionsChainEntry struct {
	Contract OptionsContract `json:"contract"`
	Quote    OptionsQuote    `json:"quote"`
}

// OptionsChain is the options-chain aggregate (api_types.OptionsChain).
type OptionsChain struct {
	UnderlyingSymbol string              `json:"underlying_symbol"`
	AsOf             *string             `json:"as_of,omitempty"`
	Contracts        []OptionsChainEntry `json:"contracts"`
}
