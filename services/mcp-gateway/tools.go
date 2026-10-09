package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

// This file registers the provider-agnostic MCP tools. Every tool:
//
//   - declares a typed input struct (the SDK infers the input schema from it and
//     rejects calls that omit a required field before the handler runs);
//   - validates and normalizes its input in a prepare method, so most invalid
//     input is rejected before the backend is called; a backend 422 that still
//     slips through is classified as ErrValidation and surfaced as an actionable
//     error rather than "no data";
//   - calls the backend through the MarketClient and shapes the result through
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
)

// noDataMessage is the successful result text used when the backend reports
// ErrNoData. A 404 can be a cached empty result within the cache TTL, so this
// is deliberately not phrased as an error or as "invalid symbol".
const noDataMessage = "No market data is available for this request."

// toolSpec packages metadata for an MCP tool registration.
type toolSpec struct {
	Name        string
	Title       string
	Description string
}

// registerTools attaches every market-data tool to server, closing over client.
func registerTools(server *mcp.Server, client *backend.MarketClient) {
	registerPriceTools(server, client)
	registerFundamentalsTools(server, client)
	registerOptionsTools(server, client)
	registerSymbolTools(server, client)
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

// runTool is the shared handler pipeline: it validates and normalizes the typed
// input via prepare, calls the backend, and maps the outcome to an MCP result
// per the T10 error contract.
func runTool[In, Req any](
	ctx context.Context,
	toolName string,
	in In,
	prepare func(In) (Req, error),
	doBackend func(context.Context, Req) (any, error),
) (*mcp.CallToolResult, any, error) {
	start := time.Now()
	slog.DebugContext(ctx, "tool invocation",
		slog.String("tool", toolName),
		slog.Any("arguments", in),
	)

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
		if errors.Is(err, backend.ErrNoData) {
			slog.DebugContext(ctx, "tool execution completed",
				slog.String("tool", toolName),
				slog.Duration("duration", duration),
				slog.String("response", noDataMessage),
			)
			return noDataResult(), nil, nil
		}

		status := 0
		detail := err.Error()
		var backendErr *backend.Error
		if errors.As(err, &backendErr) {
			status = backendErr.Status()
			detail = backendErr.Detail()
		}

		var errorClass string
		switch {
		case errors.Is(err, backend.ErrValidation):
			errorClass = "ErrValidation"
		case errors.Is(err, backend.ErrConfiguration):
			errorClass = "ErrConfiguration"
		case errors.Is(err, backend.ErrProvider):
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
	if res != nil && len(res.Content) > 0 {
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

// mapBackendError maps a MarketClient error onto a tool result:
//
//   - ErrValidation ⇒ an error result carrying the backend's validation message
//     (falling back to the generic sentinel text), so an agent can correct its
//     parameters instead of being told there is no data;
//   - ErrNoData ⇒ a successful "no data" result;
//   - ErrConfiguration / ErrProvider ⇒ an error result carrying the generic
//     sentinel text (Error hides the status/body detail);
//   - anything else ⇒ a generic catch-all error.
func mapBackendError(err error) *mcp.CallToolResult {
	switch {
	case errors.Is(err, backend.ErrValidation):
		return errorResult(errors.New(validationErrorMessage(err)))
	case errors.Is(err, backend.ErrNoData):
		return noDataResult()
	case errors.Is(err, backend.ErrConfiguration), errors.Is(err, backend.ErrProvider):
		return errorResult(err)
	default:
		return errorResult(errors.New("tool call failed"))
	}
}

// validationErrorMessage returns the agent-safe validation text carried by an
// ErrValidation Error, falling back to the generic sentinel text when the
// 422 body was unparsable.
func validationErrorMessage(err error) string {
	var backendErr *backend.Error
	if errors.As(err, &backendErr) {
		if message := backendErr.ValidationMessage(); message != "" {
			return message
		}
	}
	return backend.ErrValidation.Error()
}
