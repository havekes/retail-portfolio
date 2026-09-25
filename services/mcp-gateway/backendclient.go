package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
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
//   - ErrValidation: the request's parameters failed backend validation (422).
//     Unlike ErrNoData, retrying with corrected parameters is the right
//     response, so the parsed validation message is forwarded to the agent.
//   - ErrConfiguration: the service token was rejected. This is an operator
//     problem, not a user one.
//   - ErrProvider: the market data provider is unreachable or misbehaving.
//
// The sentinel messages are deliberately generic: they contain neither the
// service token nor any provider name, so they are safe to surface to an agent.
var (
	ErrNoData        = errors.New("no market data found")
	ErrValidation    = errors.New("market data request was invalid")
	ErrConfiguration = errors.New("market data authentication failed — check service token configuration")
	ErrProvider      = errors.New("market data is temporarily unavailable")
)

// backendError classifies a backend failure while keeping Error() generic.
//
// The underlying detail (status code and a truncated response body) is retained
// for Go-side diagnostics only; it is intentionally excluded from Error() so a
// tool handler that forwards err.Error() cannot leak internals to an agent.
//
// validation carries the agent-safe message parsed from a 422 body, if any. Only
// ErrValidation populates it.
type backendError struct {
	class      error
	status     int
	detail     string
	validation string
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

// ValidationMessage returns the agent-safe message parsed from a 422 body, or
// "" when the error is not a validation failure or the body was unparsable. It
// contains only the backend's validation text — never a status, token or
// provider name — so it is safe to forward to an agent.
func (e *backendError) ValidationMessage() string { return e.validation }

// classifyBackendError maps a non-2xx backend response onto the error taxonomy.
//
// 404 means "no data for this request"; 422 means the request's parameters
// failed backend validation; 401/403 mean the service token was rejected; every
// other status (including 5xx and unexpected 4xx) is treated as a provider-side
// failure so callers always get one of four classes.
func classifyBackendError(status int, body []byte) error {
	detail := truncateDetail(string(body))
	switch status {
	case http.StatusNotFound:
		return &backendError{class: ErrNoData, status: status, detail: detail}
	case http.StatusUnprocessableEntity:
		return &backendError{
			class:      ErrValidation,
			status:     status,
			detail:     detail,
			validation: validationMessage(body),
		}
	case http.StatusUnauthorized, http.StatusForbidden:
		return &backendError{class: ErrConfiguration, status: status, detail: detail}
	default:
		return &backendError{class: ErrProvider, status: status, detail: detail}
	}
}

// validationLocationKinds are FastAPI's request-location prefixes in a pydantic
// validation error's loc path (e.g. ["query", "expiry"]). They name where the
// invalid parameter lives, not the parameter itself, so they are dropped from
// the rendered path.
var validationLocationKinds = map[string]bool{
	"body": true, "query": true, "path": true, "header": true, "cookie": true,
}

// validationMessage extracts an agent-safe message from a FastAPI 422 body.
//
// FastAPI reports request validation failures as {"detail": ...} where detail is
// either a string or an array of {loc, msg, type} objects. Only the message text
// is echoed — never the raw body, status, or any other backend internal — so the
// result is safe to forward to an agent. Any shape that cannot be parsed falls
// back to the generic ErrValidation text.
func validationMessage(body []byte) string {
	var envelope struct {
		Detail json.RawMessage `json:"detail"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil || len(envelope.Detail) == 0 {
		return ErrValidation.Error()
	}

	var detail string
	if err := json.Unmarshal(envelope.Detail, &detail); err == nil {
		if detail = strings.TrimSpace(detail); detail != "" {
			return truncateDetail(detail)
		}
		return ErrValidation.Error()
	}

	var items []struct {
		Loc []any  `json:"loc"`
		Msg string `json:"msg"`
	}
	if err := json.Unmarshal(envelope.Detail, &items); err == nil {
		messages := make([]string, 0, len(items))
		for _, item := range items {
			msg := strings.TrimSpace(item.Msg)
			if msg == "" {
				continue
			}
			if loc := renderValidationLoc(item.Loc); loc != "" {
				messages = append(messages, loc+" "+msg)
			} else {
				messages = append(messages, msg)
			}
		}
		if len(messages) > 0 {
			return truncateDetail(strings.Join(messages, "; "))
		}
	}

	return ErrValidation.Error()
}

// renderValidationLoc renders a pydantic loc path compactly, dropping any leading
// request-location kind (e.g. ["query", "expiry"] → "expiry"). Numbers (array
// indexes) are preserved. Unsupported element types are skipped defensively.
func renderValidationLoc(loc []any) string {
	parts := make([]string, 0, len(loc))
	for i, element := range loc {
		switch value := element.(type) {
		case string:
			if i == 0 && validationLocationKinds[value] {
				continue
			}
			if value != "" {
				parts = append(parts, value)
			}
		case float64:
			parts = append(parts, strconv.FormatFloat(value, 'f', -1, 64))
		}
	}
	return strings.Join(parts, ".")
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
	env        string
}

// NewBackendClient validates baseURL and builds a client. baseURL must be an
// absolute http(s) origin; a trailing slash is tolerated. Optional env specifies
// the runtime environment ("dev", "prod"), defaulting to "dev".
func NewBackendClient(baseURL, token string, env ...string) (*BackendClient, error) {
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

	environment := defaultEnvironment
	if len(env) > 0 && strings.TrimSpace(env[0]) != "" {
		environment = strings.TrimSpace(env[0])
	}

	return &BackendClient{
		baseURL:    parsed,
		token:      token,
		httpClient: &http.Client{Timeout: defaultHTTPTimeout},
		env:        environment,
	}, nil
}

// isDev reports whether this client is running in a development environment.
func (c *BackendClient) isDev() bool {
	return isDev(c.env)
}

// Prices returns daily OHLC history for symbol.
//
// GET /api/v1/market/data/prices/{symbol}?from=&to=&exchange=
func (c *BackendClient) Prices(
	ctx context.Context,
	symbol string,
	from, to time.Time,
	exchange string,
) (json.RawMessage, error) {
	query := url.Values{}
	query.Set("from", from.Format("2006-01-02"))
	query.Set("to", to.Format("2006-01-02"))
	if exchange != "" {
		query.Set("exchange", exchange)
	}

	var out json.RawMessage
	if err := c.get(ctx, "/prices/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
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
) (json.RawMessage, error) {
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

	var out json.RawMessage
	if err := c.get(ctx, "/options/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
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
	if err := c.get(ctx, "/fundamentals/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
		return nil, err
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
// out. Every failure is normalized to one of the ErrNoData / ErrValidation /
// ErrConfiguration / ErrProvider classes.
func (c *BackendClient) get(ctx context.Context, path string, query url.Values, out any) error {
	start := time.Now()
	rawURL := c.baseURL.String() + dataPlanePath + path
	endpoint, err := url.Parse(rawURL)
	if err != nil {
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", rawURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	endpoint.RawQuery = query.Encode()
	reqURL := endpoint.String()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	req.Header.Set(serviceTokenHeader, c.token)
	req.Header.Set("Accept", "application/json")

	if c.isDev() {
		slog.DebugContext(ctx, "backend request",
			slog.String("method", http.MethodGet),
			slog.String("url", reqURL),
			slog.String("query", query.Encode()),
		)
	}

	resp, err := c.httpClient.Do(req)
	duration := time.Since(start)
	if err != nil {
		bErr := &backendError{class: ErrProvider, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", 0),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}
	defer resp.Body.Close()

	if c.isDev() {
		slog.DebugContext(ctx, "backend response",
			slog.String("method", http.MethodGet),
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.Duration("duration", duration),
		)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		bErr := &backendError{class: ErrProvider, status: resp.StatusCode, detail: err.Error()}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bErr := classifyBackendError(resp.StatusCode, body)
		var detail string
		if be, ok := bErr.(*backendError); ok {
			detail = be.Detail()
		}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.String("detail", detail),
		)
		return bErr
	}

	if err := json.Unmarshal(body, out); err != nil {
		bErr := &backendError{
			class:  ErrProvider,
			status: resp.StatusCode,
			detail: "malformed response from the market data service",
		}
		slog.ErrorContext(ctx, "backend request failed",
			slog.String("url", reqURL),
			slog.Int("status", resp.StatusCode),
			slog.String("detail", bErr.Detail()),
		)
		return bErr
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

// Statement literal values accepted by the backend statements route
// (data_router.market_data_statements). They are the only values ever placed on
// the wire.
const (
	statementIncome   = "income"
	statementBalance  = "balance"
	statementCashflow = "cashflow"
)

// IncomeStatement is one reporting period of the income statement
// (api_types.IncomeStatement). Header fields date and symbol are required;
// every line item is optional.
type IncomeStatement struct {
	Date                                    string   `json:"date"`
	Symbol                                  string   `json:"symbol"`
	ReportedCurrency                        *string  `json:"reported_currency,omitempty"`
	CIK                                     *string  `json:"cik,omitempty"`
	FillingDate                             *string  `json:"filling_date,omitempty"`
	AcceptedDate                            *string  `json:"accepted_date,omitempty"`
	FiscalYear                              *string  `json:"fiscal_year,omitempty"`
	Period                                  *string  `json:"period,omitempty"`
	Revenue                                 *Decimal `json:"revenue,omitempty"`
	CostOfRevenue                           *Decimal `json:"cost_of_revenue,omitempty"`
	GrossProfit                             *Decimal `json:"gross_profit,omitempty"`
	ResearchAndDevelopmentExpenses          *Decimal `json:"research_and_development_expenses,omitempty"`
	SellingGeneralAndAdministrativeExpenses *Decimal `json:"selling_general_and_administrative_expenses,omitempty"`
	OperatingExpenses                       *Decimal `json:"operating_expenses,omitempty"`
	OperatingIncome                         *Decimal `json:"operating_income,omitempty"`
	InterestExpense                         *Decimal `json:"interest_expense,omitempty"`
	OtherIncomeExpense                      *Decimal `json:"other_income_expense,omitempty"`
	IncomeTaxExpense                        *Decimal `json:"income_tax_expense,omitempty"`
	NetIncome                               *Decimal `json:"net_income,omitempty"`
	EPS                                     *Decimal `json:"eps,omitempty"`
	EPSDiluted                              *Decimal `json:"eps_diluted,omitempty"`
	WeightedAverageSharesOutstanding        *Decimal `json:"weighted_average_shares_outstanding,omitempty"`
	WeightedAverageSharesOutstandingDiluted *Decimal `json:"weighted_average_shares_outstanding_diluted,omitempty"`
}

// BalanceSheet is one reporting period of the balance sheet
// (api_types.BalanceSheet).
type BalanceSheet struct {
	Date                   string   `json:"date"`
	Symbol                 string   `json:"symbol"`
	ReportedCurrency       *string  `json:"reported_currency,omitempty"`
	CIK                    *string  `json:"cik,omitempty"`
	FiscalYear             *string  `json:"fiscal_year,omitempty"`
	Period                 *string  `json:"period,omitempty"`
	TotalAssets            *Decimal `json:"total_assets,omitempty"`
	CurrentAssets          *Decimal `json:"current_assets,omitempty"`
	TotalLiabilities       *Decimal `json:"total_liabilities,omitempty"`
	CurrentLiabilities     *Decimal `json:"current_liabilities,omitempty"`
	TotalDebt              *Decimal `json:"total_debt,omitempty"`
	CashAndCashEquivalents *Decimal `json:"cash_and_cash_equivalents,omitempty"`
	Inventory              *Decimal `json:"inventory,omitempty"`
	Receivables            *Decimal `json:"receivables,omitempty"`
	Payables               *Decimal `json:"payables,omitempty"`
	Goodwill               *Decimal `json:"goodwill,omitempty"`
	RetainedEarnings       *Decimal `json:"retained_earnings,omitempty"`
	TotalEquity            *Decimal `json:"total_equity,omitempty"`
	CommonStock            *Decimal `json:"common_stock,omitempty"`
	NetDebt                *Decimal `json:"net_debt,omitempty"`
}

// CashFlowStatement is one reporting period of the cash-flow statement
// (api_types.CashFlowStatement).
type CashFlowStatement struct {
	Date                   string   `json:"date"`
	Symbol                 string   `json:"symbol"`
	ReportedCurrency       *string  `json:"reported_currency,omitempty"`
	CIK                    *string  `json:"cik,omitempty"`
	FiscalYear             *string  `json:"fiscal_year,omitempty"`
	Period                 *string  `json:"period,omitempty"`
	NetIncome              *Decimal `json:"net_income,omitempty"`
	OperatingCashFlow      *Decimal `json:"operating_cash_flow,omitempty"`
	InvestingCashFlow      *Decimal `json:"investing_cash_flow,omitempty"`
	FinancingCashFlow      *Decimal `json:"financing_cash_flow,omitempty"`
	CapitalExpenditure     *Decimal `json:"capital_expenditure,omitempty"`
	FreeCashFlow           *Decimal `json:"free_cash_flow,omitempty"`
	DividendsPaid          *Decimal `json:"dividends_paid,omitempty"`
	StockBasedCompensation *Decimal `json:"stock_based_compensation,omitempty"`
	CashChange             *Decimal `json:"cash_change,omitempty"`
}

// decodeStatementList decodes the raw statements body for statement into the
// matching statement-specific Go type and returns it as any.
//
// The backend statements route returns a bare list whose item type is a union
// (income / balance / cashflow); the body is therefore fetched as json.RawMessage
// and decoded here. Unknown fields are ignored so new backend fields do not break
// decoding, and every item must carry the required date and symbol header fields.
//
// A decode failure is a plain error: the tool layer maps it onto the generic
// provider-failure result, so a cache-hit shape change is never reported as
// "no data".
func decodeStatementList(raw json.RawMessage, statement string) (any, error) {
	switch statement {
	case statementIncome:
		var items []IncomeStatement
		if err := decodeStatementItems(raw, &items); err != nil {
			return nil, err
		}
		for _, item := range items {
			if item.Date == "" || item.Symbol == "" {
				return nil, errors.New("statement item is missing the date or symbol field")
			}
		}
		return items, nil
	case statementBalance:
		var items []BalanceSheet
		if err := decodeStatementItems(raw, &items); err != nil {
			return nil, err
		}
		for _, item := range items {
			if item.Date == "" || item.Symbol == "" {
				return nil, errors.New("statement item is missing the date or symbol field")
			}
		}
		return items, nil
	case statementCashflow:
		var items []CashFlowStatement
		if err := decodeStatementItems(raw, &items); err != nil {
			return nil, err
		}
		for _, item := range items {
			if item.Date == "" || item.Symbol == "" {
				return nil, errors.New("statement item is missing the date or symbol field")
			}
		}
		return items, nil
	default:
		return nil, fmt.Errorf("unknown statement type %q", statement)
	}
}

// decodeStatementItems decodes a statement list, ignoring unknown fields.
// A JSON null body decodes to an empty list.
func decodeStatementItems(raw json.RawMessage, out any) error {
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	if err := decoder.Decode(out); err != nil {
		return fmt.Errorf("decoding statement list: %w", err)
	}
	return nil
}
