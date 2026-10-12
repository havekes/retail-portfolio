package tools

import (
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

var providerNames = []string{
	"FM" + "P",
	"Poly" + "gon",
	"EOD" + "HD",
}

type capturedRequest struct {
	path   string
	query  url.Values
	header http.Header
}

func newStubBackend(t *testing.T, status int, body string) (*httptest.Server, *capturedRequest) {
	t.Helper()
	cap := &capturedRequest{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cap.path = r.URL.Path
		cap.query = r.URL.Query()
		cap.header = r.Header.Clone()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
	t.Cleanup(srv.Close)
	return srv, cap
}

func mustClient(t *testing.T, baseURL, token string, envOpts ...string) *backend.MarketClient {
	t.Helper()
	client, err := backend.NewMarketClient(backend.Options{
		BaseURL:        baseURL,
		MaxConcurrency: 10,
	}, token)
	if err != nil {
		t.Fatalf("NewMarketClient(%q): %v", baseURL, err)
	}
	return client
}

func setSlogDefault(logger *slog.Logger) *slog.Logger {
	prev := slog.Default()
	slog.SetDefault(logger)
	return prev
}
