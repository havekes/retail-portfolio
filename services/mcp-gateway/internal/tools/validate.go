package tools

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

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

// validatePeriodParam checks that an optional period parameter is within [2, 400].
func validatePeriodParam(name string, p *int) error {
	if p != nil && (*p < 2 || *p > 400) {
		return fmt.Errorf("%s must be between 2 and 400", name)
	}
	return nil
}
