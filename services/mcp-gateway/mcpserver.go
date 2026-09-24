package main

import "github.com/modelcontextprotocol/go-sdk/mcp"

// Server identity reported to MCP clients during initialize. The name is
// provider-agnostic on purpose: an agent must never learn which upstream
// provider serves the data.
const (
	serverName    = "market-data-gateway"
	serverVersion = "0.0.1"
)

// newMCPServer builds the MCP server.
//
// T10 deliberately registers no tools: the server is the transport skeleton
// only. Tools arrive in T11, which adds a tools.go with:
//
//	func registerTools(s *mcp.Server, client *BackendClient)
//
// Contract for T11 (see the ticket plan):
//
//   - One `tools.go::registerTools(*mcp.Server, *BackendClient)` entry point
//     holding every tool. Use the generic `mcp.AddTool(server, &mcp.Tool{Name,
//     Description}, handler)` with typed `In` structs (jsonschema tags) so the
//     SDK generates input schemas.
//   - Handler shape: call the BackendClient, then return
//     `&mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: ...}}}`
//     with JSON-encoded, tool-shaped output — not the backend response verbatim.
//   - Error mapping: `errors.Is(err, ErrNoData)` is a *successful* result whose
//     text says no data is available (404 can be a cached empty result within
//     the TTL, so it is not "invalid symbol"); `ErrConfiguration` and
//     `ErrProvider` become `result.SetError(err)` using the client's generic
//     message. Never unwrap a non-ErrNoData error to surface internal detail.
//   - Tool names, descriptions, and result text must contain no provider name.
//
// The client is accepted here (rather than constructed inside) so T11 can close
// over it when registering tool handlers.
func newMCPServer(client *BackendClient) *mcp.Server {
	_ = client // consumed by T11's registerTools.
	return mcp.NewServer(&mcp.Implementation{
		Name:    serverName,
		Version: serverVersion,
	}, nil)
}
