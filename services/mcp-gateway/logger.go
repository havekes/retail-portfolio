package main

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"
)

// parseLogLevel parses a log level string case-insensitively into slog.Level.
// Supported levels: DEBUG, INFO, WARN / WARNING, ERROR.
// If levelStr is empty, defaultLevel is returned without error.
func parseLogLevel(levelStr string, defaultLevel slog.Level) (slog.Level, error) {
	trimmed := strings.ToUpper(strings.TrimSpace(levelStr))
	if trimmed == "" {
		return defaultLevel, nil
	}
	switch trimmed {
	case "DEBUG":
		return slog.LevelDebug, nil
	case "INFO":
		return slog.LevelInfo, nil
	case "WARN", "WARNING":
		return slog.LevelWarn, nil
	case "ERROR":
		return slog.LevelError, nil
	default:
		return defaultLevel, fmt.Errorf("invalid log level: %q (must be DEBUG, INFO, WARN, WARNING, or ERROR)", levelStr)
	}
}

// newLogger constructs an *slog.Logger writing to w.
// If env is "prod", a JSON handler is configured with default level slog.LevelInfo.
// Otherwise (dev, unset, etc.), a text handler is configured with default level slog.LevelDebug.
// If levelStr is non-empty, it overrides the default level.
func newLogger(w io.Writer, env string, levelStr string) (*slog.Logger, error) {
	if w == nil {
		w = os.Stdout
	}

	normEnv := strings.ToLower(strings.TrimSpace(env))
	var defaultLevel slog.Level
	if normEnv == "prod" {
		defaultLevel = slog.LevelInfo
	} else {
		defaultLevel = slog.LevelDebug
	}

	level := defaultLevel
	if strings.TrimSpace(levelStr) != "" {
		var err error
		level, err = parseLogLevel(levelStr, defaultLevel)
		if err != nil {
			return nil, err
		}
	}

	opts := &slog.HandlerOptions{
		Level: level,
	}

	var handler slog.Handler
	if normEnv == "prod" {
		handler = slog.NewJSONHandler(w, opts)
	} else {
		handler = slog.NewTextHandler(w, opts)
	}

	return slog.New(handler), nil
}

// initLogger constructs an *slog.Logger from cfg and sets it as the default slog logger.
func initLogger(cfg Config) (*slog.Logger, error) {
	logger, err := newLogger(os.Stdout, cfg.Environment, cfg.LogLevel)
	if err != nil {
		return nil, err
	}
	slog.SetDefault(logger)
	return logger, nil
}
