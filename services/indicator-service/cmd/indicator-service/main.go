package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"retail-portfolio/services/indicator-service/internal/config"
	"retail-portfolio/services/indicator-service/internal/httpapi"
	"retail-portfolio/services/indicator-service/internal/logging"
)

func main() {
	cfg, err := config.Load(os.Getenv)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	logger, err := logging.SetupLogger(cfg.Environment, cfg.LogLevel, os.Stdout)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to setup logger: %v\n", err)
		os.Exit(1)
	}
	slog.SetDefault(logger)

	router := httpapi.NewRouter(logger)

	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Server run context for graceful shutdown
	serverCtx, serverStopCtx := context.WithCancel(context.Background())

	// Listen for syscall signals for process to interrupt/quit
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGHUP, syscall.SIGINT, syscall.SIGTERM, syscall.SIGQUIT)

	go func() {
		<-sig

		// Shutdown signal with grace period of 10 seconds
		shutdownCtx, shutdownCancel := context.WithTimeout(serverCtx, 10*time.Second)
		defer shutdownCancel()

		go func() {
			<-shutdownCtx.Done()
			if errors.Is(shutdownCtx.Err(), context.DeadlineExceeded) {
				logger.Warn("graceful shutdown timed out.. forcing exit",
					slog.String("service", "indicator-service"),
					slog.String("port", cfg.Port),
					slog.String("environment", cfg.Environment),
				)
			}
		}()

		// Trigger graceful shutdown
		err := server.Shutdown(shutdownCtx)
		if err != nil {
			logger.Error("server shutdown error",
				slog.String("service", "indicator-service"),
				slog.String("port", cfg.Port),
				slog.String("environment", cfg.Environment),
				slog.String("error", err.Error()),
			)
		}
		serverStopCtx()
	}()

	logger.Info("indicator-service listening",
		slog.String("service", "indicator-service"),
		slog.String("port", cfg.Port),
		slog.String("environment", cfg.Environment),
	)
	err = server.ListenAndServe()
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server failed to start",
			slog.String("service", "indicator-service"),
			slog.String("port", cfg.Port),
			slog.String("environment", cfg.Environment),
			slog.String("error", err.Error()),
		)
		os.Exit(1)
	}

	// Wait for server context to be stopped
	<-serverCtx.Done()
	logger.Info("indicator-service stopped",
		slog.String("service", "indicator-service"),
		slog.String("port", cfg.Port),
		slog.String("environment", cfg.Environment),
	)
}
