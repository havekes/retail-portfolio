package main

import "github.com/modelcontextprotocol/go-sdk/mcp"

// Server identity reported to MCP clients during initialize. The name is
// provider-agnostic on purpose: an agent must never learn which upstream
// provider serves the data.
const (
	serverName    = "market-data-gateway"
	serverVersion = "0.0.1"
)

// newMCPServer builds the MCP server and registers every market-data tool.
//
// Tools are registered by tools.go::registerTools, which closes over the
// BackendClient. The server identity and every tool name, description and
// result string are provider-agnostic on purpose: an agent must never learn
// which upstream provider serves the data.
//
// The tool contract:
//
//   - Each tool uses the generic `mcp.AddTool(server, &mcp.Tool{Name,
//     Description}, handler)` with a typed `In` struct (jsonschema tags) so the
//     SDK generates and validates the input schema.
//   - Handlers validate/normalize their input, call the BackendClient, then
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
func newMCPServer(client *BackendClient) *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{
		Name:    serverName,
		Version: serverVersion,
	}, nil)
	registerTools(server, client)
	return server
}
