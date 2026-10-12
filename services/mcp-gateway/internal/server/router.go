package server

import (
	"encoding/json"
	"net/http"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"retail-portfolio/services/mcp-gateway/internal/config"
)

// healthResponse is a fixed liveness payload that does not depend on backend
// reachability.
var healthResponse = json.RawMessage(`{"status":"ok"}`)

var newStreamableHTTPHandler = mcp.NewStreamableHTTPHandler

// NewRouter wires the liveness probe and the MCP streamable HTTP endpoint.
//
// The MCP listener is unauthenticated: the shared-secret trust boundary is the
// backend data plane (T08/T09), not the MCP transport. Cross-origin browser
// requests are rejected via http.NewCrossOriginProtection.
func NewRouter(server *mcp.Server, cfg config.Config) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mcpHandler := newStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server },
		&mcp.StreamableHTTPOptions{
			SessionTimeout: cfg.SessionIdleTimeout,
		},
	)
	mux.Handle("/mcp", http.NewCrossOriginProtection().Handler(mcpHandler))
	return mux
}

// healthHandler serves GET /health with a fixed 200 payload.
func healthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(healthResponse)
}
