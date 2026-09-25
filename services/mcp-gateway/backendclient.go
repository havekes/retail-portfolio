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

// isDev reports whether this client is running in a development environment.
func (c *BackendClient) isDev() bool {
	return isDev(c.cfg.Environment)
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
	if err := c.group.Get(ctx, "/prices/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
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
	if err := c.group.Get(ctx, "/options/"+url.PathEscape(normalizeSymbol(symbol)), query, &out); err != nil {
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
