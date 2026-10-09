package server

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
	"retail-portfolio/services/mcp-gateway/internal/tools"
)

// Server identity reported to MCP clients during initialize. The name is
// provider-agnostic on purpose: an agent must never learn which upstream
// provider serves the data.
const (
	ServerName    = "market-data-gateway"
	ServerVersion = "0.0.1"
)

// New builds the MCP server and registers every market-data tool.
//
// Tools are registered by tools.Register, which closes over the MarketClient.
// The server identity and every tool name, description and result string are
// provider-agnostic on purpose: an agent must never learn which upstream
// provider serves the data.
//
// The tool contract:
//
//   - Each tool is registered with a `toolSpec` (Name, Title, Description) via
//     `addTool`, setting `Annotations` with `ReadOnlyHint: true`, `IdempotentHint: true`,
//     and `Title`. Input schemas are inferred from typed `In` structs (jsonschema tags).
//   - Descriptions follow a structured format with four labelled sections:
//     "Use when:", "Examples:", "Returns:", and "See also:".
//   - Handlers validate/normalize their input, call the MarketClient, then
//     return a `&mcp.CallToolResult` with JSON-encoded, tool-shaped output as
//     `mcp.TextContent` — not the backend response verbatim.
//   - Error mapping: `errors.Is(err, ErrNoData)` is a *successful* result whose
//     text says no data is available (404 can be a cached empty result within
//     the TTL, so it is not "invalid symbol"); `ErrValidation` becomes
//     `result.SetError` carrying the parsed, agent-safe validation message;
//     `ErrConfiguration` and `ErrProvider` become `result.SetError(err)` using
//     the client's generic message. Backend status/body detail is never
//     unwrapped; only the parsed validation message is forwarded.
//   - Tool names, descriptions, and result text contain no provider name.
func New(client *backend.MarketClient) *mcp.Server {
	s := mcp.NewServer(&mcp.Implementation{
		Name:    ServerName,
		Version: ServerVersion,
	}, nil)
	tools.Register(s, client)
	return s
}
