package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func newTestRouter(t *testing.T) http.Handler {
	t.Helper()
	cfg := Config{
		Environment:        "dev",
		SessionIdleTimeout: 30 * time.Minute,
	}
	client := mustClient(t, "http://backend.invalid", "test-token")
	return newRouter(newMCPServer(client, cfg), cfg)
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

func TestRouter_SessionTimeoutConfigured(t *testing.T) {
	origHandler := newStreamableHTTPHandler
	defer func() { newStreamableHTTPHandler = origHandler }()

	var capturedOpts *mcp.StreamableHTTPOptions
	newStreamableHTTPHandler = func(getServer func(*http.Request) *mcp.Server, opts *mcp.StreamableHTTPOptions) *mcp.StreamableHTTPHandler {
		capturedOpts = opts
		return origHandler(getServer, opts)
	}

	cfg := Config{
		Environment:        "dev",
		SessionIdleTimeout: 5 * time.Minute,
	}
	client := mustClient(t, "http://backend.invalid", "test-token")
	_ = newRouter(newMCPServer(client, cfg), cfg)

	if capturedOpts == nil {
		t.Fatal("expected newStreamableHTTPHandler to be called with options")
	}
	if capturedOpts.SessionTimeout != 5*time.Minute {
		t.Errorf("SessionTimeout = %v, want %v", capturedOpts.SessionTimeout, 5*time.Minute)
	}
}

func TestMCPCrossOriginProtection(t *testing.T) {
	srv := httptest.NewServer(newTestRouter(t))
	t.Cleanup(srv.Close)

	postPayload := `{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.0.1"}}}`

	t.Run("rejects Sec-Fetch-Site cross-site with 403", func(t *testing.T) {
		req, err := http.NewRequest(http.MethodPost, srv.URL+"/mcp", strings.NewReader(postPayload))
		if err != nil {
			t.Fatalf("new request: %v", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Sec-Fetch-Site", "cross-site")

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("POST /mcp: %v", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusForbidden {
			t.Errorf("status = %d, want 403 Forbidden", resp.StatusCode)
		}
	})

	t.Run("rejects mismatched Origin with 403", func(t *testing.T) {
		req, err := http.NewRequest(http.MethodPost, srv.URL+"/mcp", strings.NewReader(postPayload))
		if err != nil {
			t.Fatalf("new request: %v", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Origin", "http://evil.example.com")

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("POST /mcp: %v", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusForbidden {
			t.Errorf("status = %d, want 403 Forbidden", resp.StatusCode)
		}
	})

	t.Run("allows non-browser POST without cross-origin headers", func(t *testing.T) {
		req, err := http.NewRequest(http.MethodPost, srv.URL+"/mcp", strings.NewReader(postPayload))
		if err != nil {
			t.Fatalf("new request: %v", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json, text/event-stream")

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatalf("POST /mcp: %v", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			t.Errorf("status = %d, want 200 OK", resp.StatusCode)
		}
	})
}
