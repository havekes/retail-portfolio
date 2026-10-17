package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"retail-portfolio/services/mcp-gateway/internal/backend"
	"retail-portfolio/services/mcp-gateway/internal/config"
	"retail-portfolio/services/mcp-gateway/internal/logging"
	"retail-portfolio/services/mcp-gateway/internal/observability"
	"retail-portfolio/services/mcp-gateway/internal/server"
)

func main() {
	cfg, err := config.Load(os.Getenv)
	if err != nil {
		slog.Error("mcp-gateway configuration error", slog.Any("error", err))
		os.Exit(1)
	}

	if _, err := logging.Init(cfg); err != nil {
		slog.Error("mcp-gateway logger initialization error", slog.Any("error", err))
		os.Exit(1)
	}

	logger := slog.With(
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("data_plane_path", cfg.DataPlanePath),
		slog.String("environment", cfg.Environment),
		slog.Int("max_concurrency", cfg.MaxConcurrency),
	)

	client, err := backend.NewMarketClient(backend.Options{
		BaseURL:        cfg.BackendBaseURL,
		MaxConcurrency: cfg.MaxConcurrency,
		DataPlanePath:  cfg.DataPlanePath,
	}, cfg.ServiceToken)
	if err != nil {
		logger.Error("mcp-gateway backend client error", slog.Any("error", err))
		os.Exit(1)
	}

	// Initialise telemetry before the router is built so tracers resolve to
	// the configured provider, and keep the shutdown handle to flush spans on exit.
	shutdownOTel := observability.SetupOTel(context.Background(), cfg)

	router := server.NewRouter(server.New(client), cfg)
	handler := logging.Middleware(otelhttp.NewHandler(router, "mcp-gateway.http"), cfg.Environment)

	httpServer := &http.Server{
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
		logger.Info("mcp-gateway shutting down")

		// Shutdown signal with grace period of 10 seconds
		shutdownCtx, shutdownCancel := context.WithTimeout(serverCtx, 10*time.Second)
		defer shutdownCancel()

		go func() {
			<-shutdownCtx.Done()
			if errors.Is(shutdownCtx.Err(), context.DeadlineExceeded) {
				logger.Error("graceful shutdown timed out.. forcing exit")
			}
		}()

		// Trigger graceful shutdown
		err := httpServer.Shutdown(shutdownCtx)
		if err != nil {
			logger.Error("server shutdown error", slog.Any("error", err))
		}
		serverStopCtx()
	}()

	logger.Info("mcp-gateway listening")
	err = httpServer.ListenAndServe()
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server failed to start", slog.Any("error", err))
		os.Exit(1)
	}

	// Wait for server context to be stopped
	<-serverCtx.Done()

	// Flush pending spans before the process exits.
	flushCtx, flushCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer flushCancel()
	if err := shutdownOTel(flushCtx); err != nil {
		logger.Error("otel shutdown error", slog.Any("error", err))
	}

	logger.Info("mcp-gateway stopped")
}
