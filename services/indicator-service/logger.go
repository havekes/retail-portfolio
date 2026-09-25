package main

import (
	"io"
	"log/slog"
	"os"
	"strings"
)

// ParseLogLevel parses a log level string case-insensitively.
// Supported levels: DEBUG, INFO, WARN / WARNING, ERROR.
// Falls back to defaultLevel if empty or invalid.
func ParseLogLevel(levelStr string, defaultLevel slog.Level) slog.Level {
	switch strings.ToUpper(strings.TrimSpace(levelStr)) {
	case "DEBUG":
		return slog.LevelDebug
	case "INFO":
		return slog.LevelInfo
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return defaultLevel
	}
}

// SetupLogger initializes an *slog.Logger according to the environment and log level.
// When env is "prod" (case-insensitive), a JSON handler is used with default level slog.LevelInfo.
// Otherwise (dev or unset), a human-readable text handler is used with default level slog.LevelDebug.
// If logLevel is provided, it overrides the default level.
// If out is nil, os.Stdout is used as the destination writer.
func SetupLogger(env, logLevel string, out io.Writer) *slog.Logger {
	if out == nil {
		out = os.Stdout
	}

	var (
		defaultLevel slog.Level
		isProd       = strings.EqualFold(strings.TrimSpace(env), "prod")
	)

	if isProd {
		defaultLevel = slog.LevelInfo
	} else {
		defaultLevel = slog.LevelDebug
	}

	level := ParseLogLevel(logLevel, defaultLevel)
	opts := &slog.HandlerOptions{
		Level: level,
	}

	var handler slog.Handler
	if isProd {
		handler = slog.NewJSONHandler(out, opts)
	} else {
		handler = slog.NewTextHandler(out, opts)
	}

	return slog.New(handler)
}
