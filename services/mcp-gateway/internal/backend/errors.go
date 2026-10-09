package backend

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
)

// errorDetailLimit caps the diagnostic detail retained on an Error.
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

// Error classifies a backend failure while keeping Error() generic.
//
// The underlying detail (status code and a truncated response body) is retained
// for Go-side diagnostics only; it is intentionally excluded from Error() so a
// tool handler that forwards err.Error() cannot leak internals to an agent.
//
// validation carries the agent-safe message parsed from a 422 body, if any. Only
// ErrValidation populates it.
type Error struct {
	class      error
	status     int
	detail     string
	validation string
}

func (e *Error) Error() string { return e.class.Error() }

// Unwrap exposes the sentinel so errors.Is(err, ErrNoData) &c. keep working.
func (e *Error) Unwrap() error { return e.class }

// Status returns the HTTP status that produced the error, or 0 for transport
// and decoding failures.
func (e *Error) Status() int { return e.status }

// Detail returns the Go-side diagnostic detail. It must not be forwarded to
// agent-facing output.
func (e *Error) Detail() string { return e.detail }

// ValidationMessage returns the agent-safe message parsed from a 422 body, or
// "" when the error is not a validation failure or the body was unparsable. It
// contains only the backend's validation text — never a status, token or
// provider name — so it is safe to forward to an agent.
func (e *Error) ValidationMessage() string { return e.validation }

// NewError constructs an *Error with class and diagnostic detail.
func NewError(class error, detail string) *Error {
	return &Error{
		class:  class,
		detail: detail,
	}
}

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
		return &Error{class: ErrNoData, status: status, detail: detail}
	case http.StatusUnprocessableEntity:
		return &Error{
			class:      ErrValidation,
			status:     status,
			detail:     detail,
			validation: validationMessage(body),
		}
	case http.StatusUnauthorized, http.StatusForbidden:
		return &Error{class: ErrConfiguration, status: status, detail: detail}
	default:
		return &Error{class: ErrProvider, status: status, detail: detail}
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

// truncateDetail clamps detail string to errorDetailLimit runes.
func truncateDetail(s string) string {
	runes := []rune(s)
	if len(runes) <= errorDetailLimit {
		return s
	}
	return string(runes[:errorDetailLimit])
}
