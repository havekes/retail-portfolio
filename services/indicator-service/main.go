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
)

func main() {
	env := os.Getenv("ENVIRONMENT")
	logLevel := os.Getenv("LOG_LEVEL")
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	logger := SetupLogger(env, logLevel, os.Stdout)
	slog.SetDefault(logger)

	router := NewRouter()

	server := &http.Server{
		Addr:         ":" + port,
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
					slog.String("port", port),
					slog.String("environment", env),
				)
			}
		}()

		// Trigger graceful shutdown
		err := server.Shutdown(shutdownCtx)
		if err != nil {
			logger.Error("server shutdown error",
				slog.String("service", "indicator-service"),
				slog.String("port", port),
				slog.String("environment", env),
				slog.String("error", err.Error()),
			)
		}
		serverStopCtx()
	}()

	logger.Info("indicator-service listening",
		slog.String("service", "indicator-service"),
		slog.String("port", port),
		slog.String("environment", env),
	)
	err := server.ListenAndServe()
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server failed to start",
			slog.String("service", "indicator-service"),
			slog.String("port", port),
			slog.String("environment", env),
			slog.String("error", err.Error()),
		)
		os.Exit(1)
	}

	// Wait for server context to be stopped
	<-serverCtx.Done()
	logger.Info("indicator-service stopped",
		slog.String("service", "indicator-service"),
		slog.String("port", port),
		slog.String("environment", env),
	)
}
