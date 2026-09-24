package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func newTestRouter(t *testing.T) http.Handler {
	t.Helper()
	client := mustClient(t, "http://backend.invalid", "test-token")
	return newRouter(newMCPServer(client))
}

func TestHealthEndpoint(t *testing.T) {
	srv := httptest.NewServer(newTestRouter(t))
	t.Cleanup(srv.Close)

	resp, err := http.Get(srv.URL + "/health")
	if err != nil {
		t.Fatalf("GET /health: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	if got := string(body); got != `{"status":"ok"}` {
		t.Errorf("body = %q, want %q", got, `{"status":"ok"}`)
	}
}

func TestHealthEndpointRejectsNonGet(t *testing.T) {
	srv := httptest.NewServer(newTestRouter(t))
	t.Cleanup(srv.Close)

	resp, err := http.Post(srv.URL+"/health", "application/json", nil)
	if err != nil {
		t.Fatalf("POST /health: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d, want 405", resp.StatusCode)
	}
	if got := resp.Header.Get("Allow"); got != http.MethodGet {
		t.Errorf("Allow = %q, want GET", got)
	}
}

func TestMCPInitializeAndToolList(t *testing.T) {
	srv := httptest.NewServer(newTestRouter(t))
	t.Cleanup(srv.Close)

	ctx := context.Background()
	client := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.1"}, nil)
	transport := &mcp.StreamableClientTransport{
		Endpoint:             srv.URL + "/mcp",
		DisableStandaloneSSE: true,
	}

	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		t.Fatalf("connect to /mcp: %v", err)
	}
	t.Cleanup(func() { _ = session.Close() })

	init := session.InitializeResult()
	if init == nil || init.ServerInfo == nil {
		t.Fatalf("initialize result missing server info: %+v", init)
	}
	if init.ServerInfo.Name != serverName {
		t.Errorf("server name = %q, want %q", init.ServerInfo.Name, serverName)
	}

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		t.Fatalf("tools/list: %v", err)
	}

	got := make(map[string]*mcp.Tool, len(tools.Tools))
	for _, tool := range tools.Tools {
		got[tool.Name] = tool
	}
	if len(got) != len(expectedToolNames) {
		t.Errorf("tool count = %d, want %d: %+v", len(got), len(expectedToolNames), tools.Tools)
	}
	for _, name := range expectedToolNames {
		if _, ok := got[name]; !ok {
			t.Errorf("tool %q is not registered", name)
		}
	}

	// Criterion: no tool name or description may mention an upstream provider.
	for _, tool := range tools.Tools {
		assertNoProviderName(t, "tool name", tool.Name)
		assertNoProviderName(t, "tool description", tool.Description)
	}
}
