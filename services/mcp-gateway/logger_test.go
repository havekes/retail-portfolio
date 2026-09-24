package main

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"strings"
	"testing"
)

func TestParseLogLevel(t *testing.T) {
	tests := []struct {
		name         string
		levelStr     string
		defaultLevel slog.Level
		expected     slog.Level
		expectErr    bool
	}{
		{"DEBUG uppercase", "DEBUG", slog.LevelInfo, slog.LevelDebug, false},
		{"DEBUG lowercase", "debug", slog.LevelInfo, slog.LevelDebug, false},
		{"DEBUG whitespace", "  DEBUG  ", slog.LevelInfo, slog.LevelDebug, false},
		{"INFO uppercase", "INFO", slog.LevelDebug, slog.LevelInfo, false},
		{"INFO lowercase", "info", slog.LevelDebug, slog.LevelInfo, false},
		{"WARN uppercase", "WARN", slog.LevelDebug, slog.LevelWarn, false},
		{"WARN lowercase", "warn", slog.LevelDebug, slog.LevelWarn, false},
		{"WARNING uppercase", "WARNING", slog.LevelDebug, slog.LevelWarn, false},
		{"WARNING lowercase", "warning", slog.LevelDebug, slog.LevelWarn, false},
		{"ERROR uppercase", "ERROR", slog.LevelDebug, slog.LevelError, false},
		{"ERROR lowercase", "error", slog.LevelDebug, slog.LevelError, false},
		{"empty string fallback to default", "", slog.LevelWarn, slog.LevelWarn, false},
		{"whitespace fallback to default", "   ", slog.LevelError, slog.LevelError, false},
		{"invalid string returns error", "UNKNOWN", slog.LevelInfo, slog.LevelInfo, true},
		{"invalid level string returns error", "INVALID_LEVEL", slog.LevelDebug, slog.LevelDebug, true},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			actual, err := parseLogLevel(tc.levelStr, tc.defaultLevel)
			if tc.expectErr {
				if err == nil {
					t.Errorf("parseLogLevel(%q) expected error, got nil", tc.levelStr)
				}
			} else {
				if err != nil {
					t.Errorf("parseLogLevel(%q) unexpected error: %v", tc.levelStr, err)
				}
				if actual != tc.expected {
					t.Errorf("parseLogLevel(%q) = %v, want %v", tc.levelStr, actual, tc.expected)
				}
			}
		})
	}
}

func TestLogger_HandlerSelection(t *testing.T) {
	tests := []struct {
		name        string
		env         string
		expectJSON  bool
		expectDebug bool
		expectInfo  bool
	}{
		{
			name:        "prod environment uses JSONHandler and INFO default level",
			env:         "prod",
			expectJSON:  true,
			expectDebug: false,
			expectInfo:  true,
		},
		{
			name:        "PROD uppercase environment uses JSONHandler and INFO default level",
			env:         "PROD",
			expectJSON:  true,
			expectDebug: false,
			expectInfo:  true,
		},
		{
			name:        "prod with whitespace uses JSONHandler and INFO default level",
			env:         "  prod  ",
			expectJSON:  true,
			expectDebug: false,
			expectInfo:  true,
		},
		{
			name:        "dev environment uses TextHandler and DEBUG default level",
			env:         "dev",
			expectJSON:  false,
			expectDebug: true,
			expectInfo:  true,
		},
		{
			name:        "DEV uppercase environment uses TextHandler and DEBUG default level",
			env:         "DEV",
			expectJSON:  false,
			expectDebug: true,
			expectInfo:  true,
		},
		{
			name:        "unset environment uses TextHandler and DEBUG default level",
			env:         "",
			expectJSON:  false,
			expectDebug: true,
			expectInfo:  true,
		},
		{
			name:        "whitespace environment uses TextHandler and DEBUG default level",
			env:         "   ",
			expectJSON:  false,
			expectDebug: true,
			expectInfo:  true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var buf bytes.Buffer
			logger, err := newLogger(&buf, tc.env, "")
			if err != nil {
				t.Fatalf("unexpected error from newLogger: %v", err)
			}

			// Verify handler type
			if tc.expectJSON {
				if _, ok := logger.Handler().(*slog.JSONHandler); !ok {
					t.Errorf("expected *slog.JSONHandler for env %q, got %T", tc.env, logger.Handler())
				}
			} else {
				if _, ok := logger.Handler().(*slog.TextHandler); !ok {
					t.Errorf("expected *slog.TextHandler for env %q, got %T", tc.env, logger.Handler())
				}
			}

			// Verify debug level logging
			buf.Reset()
			logger.Debug("debug message", slog.String("field", "val"))
			debugLogged := buf.Len() > 0
			if debugLogged != tc.expectDebug {
				t.Errorf("Debug logged = %v, want %v (output: %q)", debugLogged, tc.expectDebug, buf.String())
			}

			// Verify info level logging
			buf.Reset()
			logger.Info("info message", slog.String("field", "val"))
			infoLogged := buf.Len() > 0
			if infoLogged != tc.expectInfo {
				t.Errorf("Info logged = %v, want %v (output: %q)", infoLogged, tc.expectInfo, buf.String())
			}

			// Verify output format
			output := strings.TrimSpace(buf.String())
			if tc.expectJSON {
				if !json.Valid([]byte(output)) {
					t.Errorf("expected valid JSON line, got: %s", output)
				}
				var parsed map[string]any
				if err := json.Unmarshal([]byte(output), &parsed); err != nil {
					t.Fatalf("failed to unmarshal JSON log: %v", err)
				}
				if parsed["msg"] != "info message" {
					t.Errorf("expected msg 'info message', got: %v", parsed["msg"])
				}
				if parsed["level"] != "INFO" {
					t.Errorf("expected level 'INFO', got: %v", parsed["level"])
				}
				if parsed["field"] != "val" {
					t.Errorf("expected field 'val', got: %v", parsed["field"])
				}
			} else {
				if !strings.Contains(output, "level=INFO") {
					t.Errorf("expected level=INFO in text output, got: %s", output)
				}
				if !strings.Contains(output, "msg=\"info message\"") && !strings.Contains(output, "msg=info message") {
					t.Errorf("expected msg in text output, got: %s", output)
				}
				if !strings.Contains(output, "field=val") {
					t.Errorf("expected field=val in text output, got: %s", output)
				}
			}
		})
	}
}

func TestLogger_LogLevelOverride(t *testing.T) {
	tests := []struct {
		name        string
		env         string
		levelStr    string
		expectDebug bool
		expectInfo  bool
		expectWarn  bool
		expectErr   bool
	}{
		{
			name:        "prod overridden to DEBUG",
			env:         "prod",
			levelStr:    "DEBUG",
			expectDebug: true,
			expectInfo:  true,
			expectWarn:  true,
			expectErr:   false,
		},
		{
			name:        "prod overridden to WARN",
			env:         "prod",
			levelStr:    "WARN",
			expectDebug: false,
			expectInfo:  false,
			expectWarn:  true,
			expectErr:   false,
		},
		{
			name:        "dev overridden to INFO",
			env:         "dev",
			levelStr:    "INFO",
			expectDebug: false,
			expectInfo:  true,
			expectWarn:  true,
			expectErr:   false,
		},
		{
			name:        "dev overridden to WARN",
			env:         "dev",
			levelStr:    "WARN",
			expectDebug: false,
			expectInfo:  false,
			expectWarn:  true,
			expectErr:   false,
		},
		{
			name:        "dev overridden to ERROR",
			env:         "dev",
			levelStr:    "ERROR",
			expectDebug: false,
			expectInfo:  false,
			expectWarn:  false,
			expectErr:   false,
		},
		{
			name:      "invalid log level returns error",
			env:       "prod",
			levelStr:  "INVALID_LEVEL",
			expectErr: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var buf bytes.Buffer
			logger, err := newLogger(&buf, tc.env, tc.levelStr)
			if tc.expectErr {
				if err == nil {
					t.Fatalf("expected error for levelStr %q, got nil", tc.levelStr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			buf.Reset()
			logger.Debug("debug message")
			if (buf.Len() > 0) != tc.expectDebug {
				t.Errorf("Debug emitted = %v, want %v", buf.Len() > 0, tc.expectDebug)
			}

			buf.Reset()
			logger.Info("info message")
			if (buf.Len() > 0) != tc.expectInfo {
				t.Errorf("Info emitted = %v, want %v", buf.Len() > 0, tc.expectInfo)
			}

			buf.Reset()
			logger.Warn("warn message")
			if (buf.Len() > 0) != tc.expectWarn {
				t.Errorf("Warn emitted = %v, want %v", buf.Len() > 0, tc.expectWarn)
			}
		})
	}
}

func TestLogger_TokenRedaction(t *testing.T) {
	const secretToken = "super-secret-market-data-token-987"
	cfg := Config{
		BackendBaseURL: "http://backend:8000",
		ServiceToken:   secretToken,
		Port:           "8080",
		Environment:    "prod",
		LogLevel:       "INFO",
	}

	var buf bytes.Buffer
	logger, err := newLogger(&buf, cfg.Environment, cfg.LogLevel)
	if err != nil {
		t.Fatalf("unexpected error creating logger: %v", err)
	}

	// Startup logging
	logger.Info("mcp-gateway listening",
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("environment", cfg.Environment),
	)

	// Shutdown logging
	logger.Info("mcp-gateway shutting down",
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("environment", cfg.Environment),
	)

	logger.Info("mcp-gateway stopped",
		slog.String("service", "mcp-gateway"),
		slog.String("port", cfg.Port),
		slog.String("backend_url", cfg.BackendBaseURL),
		slog.String("environment", cfg.Environment),
	)

	output := buf.String()

	// Assert required attributes appear in log output
	for _, expectedAttr := range []string{"service", "mcp-gateway", "port", "8080", "backend_url", "http://backend:8000", "environment", "prod"} {
		if !strings.Contains(output, expectedAttr) {
			t.Errorf("expected log output to contain attribute %q, got: %s", expectedAttr, output)
		}
	}

	// Assert secret token and token env var name never appear
	if strings.Contains(output, secretToken) {
		t.Fatalf("log output leaked secret token value: %s", output)
	}
	if strings.Contains(output, "MARKET_DATA_SERVICE_TOKEN") {
		t.Fatalf("log output contained MARKET_DATA_SERVICE_TOKEN: %s", output)
	}
}

func TestInitLogger(t *testing.T) {
	cfg := Config{
		BackendBaseURL: "http://backend:8000",
		ServiceToken:   "test-token",
		Port:           "8080",
		Environment:    "dev",
		LogLevel:       "DEBUG",
	}

	logger, err := initLogger(cfg)
	if err != nil {
		t.Fatalf("unexpected error from initLogger: %v", err)
	}
	if logger == nil {
		t.Fatal("expected non-nil logger from initLogger")
	}

	// Ensure slog.Default() is now the logger
	if slog.Default() != logger {
		t.Errorf("slog.Default() was not updated by initLogger")
	}
}
