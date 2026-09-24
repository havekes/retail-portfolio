package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// healthResponse is a fixed liveness payload that does not depend on backend
// reachability.
var healthResponse = json.RawMessage(`{"status":"ok"}`)

func main() {
	cfg, err := loadConfig(os.Getenv)
	if err != nil {
		slog.Error("mcp-gateway configuration error", slog.Any("error", err))
		os.Exit(1)
	}

	if _, err := initLogger(cfg); err != nil {
		slog.Error("mcp-gateway logger initialization error", slog.Any("error", err))
		os.Exit(1)
	}

	client, err := NewBackendClient(cfg.BackendBaseURL, cfg.ServiceToken, cfg.Environment)
	if err != nil {
		slog.Error("mcp-gateway backend client error",
			slog.String("service", "mcp-gateway"),
			slog.String("port", cfg.Port),
			slog.String("backend_url", cfg.BackendBaseURL),
			slog.String("environment", cfg.Environment),
			slog.Any("error", err),
		)
		os.Exit(1)
	}

	router := newRouter(newMCPServer(client, cfg.Environment))
	handler := loggingMiddleware(router, cfg.Environment)

	server := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: handler,
		// ReadTimeout bounds how long a client may take to send a request.
		ReadTimeout: 15 * time.Second,
		// WriteTimeout is deliberately unlimited (0): the MCP streamable HTTP
		// transport keeps SSE/streaming responses open for as long as the
		// session lives, and any finite deadline would truncate them mid-stream.
		// IdleTimeout still reaps dead connections.
		WriteTimeout: 0,
		IdleTimeout:  60 * time.Second,
	}

	// Server run context for graceful shutdown
	serverCtx, serverStopCtx := context.WithCancel(context.Background())

	// Listen for syscall signals for process to interrupt/quit
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGHUP, syscall.SIGINT, syscall.SIGTERM, syscall.SIGQUIT)

	go func() {
		<-sig
		slog.Info("mcp-gateway shutting down",
			slog.String("service", "mcp-gateway"),
			slog.String("port", cfg.Port),
			slog.String("backend_url", cfg.BackendBaseURL),
			slog.String("environment", cfg.Environment),
		)

		// Shutdown signal with grace period of 10 seconds
		shutdownCtx, shutdownCancel := context.WithTimeout(serverCtx, 10*time.Second)
		defer shutdownCancel()

		go func() {
			<-shutdownCtx.Done()
			if errors.Is(shutdownCtx.Err(), context.DeadlineExceeded) {
				slog.Error("graceful shutdown timed out.. forcing exit",
					slog.String("service", "mcp-gateway"),
					slog.String("port", cfg.Port),
					slog.String("backend_url", cfg.BackendBaseURL),
					slog.String("environment", cfg.Environment),
				)
			}
		}()

		// Trigger graceful shutdown
		err := server.Shutdown(shutdownCtx)
		if err != nil {
			slog.Error("server shutdown error",
				slog.String("service", "mcp-gateway"),
				slog.String("port", cfg.Port),
				slog.String("backend_url", cfg.BackendBaseURL),
				slog.String("environment", cfg.Environment),
				slog.Any("error", err),
			)
		}
		serverStopCtx()
	}()

	slog.Info("mcp-gateway listening",
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("environment", cfg.Environment),
	)
	err = server.ListenAndServe()
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server failed to start",
			slog.String("service", "mcp-gateway"),
			slog.String("port", cfg.Port),
			slog.String("backend_url", cfg.BackendBaseURL),
			slog.String("environment", cfg.Environment),
			slog.Any("error", err),
		)
		os.Exit(1)
	}

	// Wait for server context to be stopped
	<-serverCtx.Done()
	slog.Info("mcp-gateway stopped",
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("environment", cfg.Environment),
	)
}

// newRouter wires the liveness probe and the MCP streamable HTTP endpoint.
//
// The MCP listener is unauthenticated: the shared-secret trust boundary is the
// backend data plane (T08/T09), not the MCP transport.
func newRouter(server *mcp.Server) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.Handle("/mcp", mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server },
		nil,
	))
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
