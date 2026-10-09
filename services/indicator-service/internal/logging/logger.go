package logging

import (
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"
)

// ParseLogLevel parses a log level string case-insensitively into slog.Level.
// Supported levels: DEBUG, INFO, WARN / WARNING, ERROR.
// If levelStr is empty, defaultLevel is returned without error.
// If levelStr is invalid, an error is returned.
func ParseLogLevel(levelStr string, defaultLevel slog.Level) (slog.Level, error) {
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

// SetupLogger initializes an *slog.Logger according to the environment and log level.
// When env is "prod" (case-insensitive), a JSON handler is used with default level slog.LevelInfo.
// Otherwise (dev or unset), a human-readable text handler is used with default level slog.LevelDebug.
// If logLevel is provided, it overrides the default level.
// If out is nil, os.Stdout is used as the destination writer.
func SetupLogger(env, logLevel string, out io.Writer) (*slog.Logger, error) {
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

	level, err := ParseLogLevel(logLevel, defaultLevel)
	if err != nil {
		return nil, err
	}
	opts := &slog.HandlerOptions{
		Level: level,
	}

	var handler slog.Handler
	if isProd {
		handler = slog.NewJSONHandler(out, opts)
	} else {
		handler = slog.NewTextHandler(out, opts)
	}

	return slog.New(handler), nil
}
