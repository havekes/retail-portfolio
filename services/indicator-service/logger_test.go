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
	}{
		{"DEBUG uppercase", "DEBUG", slog.LevelInfo, slog.LevelDebug},
		{"DEBUG lowercase", "debug", slog.LevelInfo, slog.LevelDebug},
		{"DEBUG mixedcase with whitespace", "  Debug ", slog.LevelInfo, slog.LevelDebug},
		{"INFO uppercase", "INFO", slog.LevelDebug, slog.LevelInfo},
		{"INFO lowercase", "info", slog.LevelDebug, slog.LevelInfo},
		{"WARN uppercase", "WARN", slog.LevelDebug, slog.LevelWarn},
		{"WARN lowercase", "warn", slog.LevelDebug, slog.LevelWarn},
		{"WARNING uppercase", "WARNING", slog.LevelDebug, slog.LevelWarn},
		{"WARNING lowercase", "warning", slog.LevelDebug, slog.LevelWarn},
		{"ERROR uppercase", "ERROR", slog.LevelDebug, slog.LevelError},
		{"ERROR lowercase", "error", slog.LevelDebug, slog.LevelError},
		{"empty string fallback to default", "", slog.LevelWarn, slog.LevelWarn},
		{"whitespace fallback to default", "   ", slog.LevelError, slog.LevelError},
		{"invalid string fallback to default", "UNKNOWN", slog.LevelInfo, slog.LevelInfo},
		{"invalid string fallback to debug", "invalid_level", slog.LevelDebug, slog.LevelDebug},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			actual := ParseLogLevel(tc.levelStr, tc.defaultLevel)
			if actual != tc.expected {
				t.Errorf("ParseLogLevel(%q, %v) = %v; want %v", tc.levelStr, tc.defaultLevel, actual, tc.expected)
			}
		})
	}
}

func TestSetupLogger_HandlerAndLevel(t *testing.T) {
	tests := []struct {
		name       string
		env        string
		logLevel   string
		expectJSON bool
		emitDebug  bool
		emitInfo   bool
		emitWarn   bool
		emitError  bool
	}{
		{
			name:       "prod default INFO (JSON)",
			env:        "prod",
			logLevel:   "",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "PROD uppercase default INFO (JSON)",
			env:        "PROD",
			logLevel:   "",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "prod with whitespace",
			env:        "  prod  ",
			logLevel:   "",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "prod overridden to DEBUG",
			env:        "prod",
			logLevel:   "DEBUG",
			expectJSON: true,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "prod overridden to debug lowercase",
			env:        "prod",
			logLevel:   "debug",
			expectJSON: true,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "prod overridden to WARN",
			env:        "prod",
			logLevel:   "WARN",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   false,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "prod overridden to ERROR",
			env:        "prod",
			logLevel:   "ERROR",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   false,
			emitWarn:   false,
			emitError:  true,
		},
		{
			name:       "prod with invalid log level falls back to INFO",
			env:        "prod",
			logLevel:   "invalid",
			expectJSON: true,
			emitDebug:  false,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "dev default DEBUG (Text)",
			env:        "dev",
			logLevel:   "",
			expectJSON: false,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "dev uppercase default DEBUG (Text)",
			env:        "DEV",
			logLevel:   "",
			expectJSON: false,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "unset env default DEBUG (Text)",
			env:        "",
			logLevel:   "",
			expectJSON: false,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "whitespace env default DEBUG (Text)",
			env:        "   ",
			logLevel:   "",
			expectJSON: false,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "dev overridden to INFO",
			env:        "dev",
			logLevel:   "INFO",
			expectJSON: false,
			emitDebug:  false,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "dev overridden to WARN",
			env:        "dev",
			logLevel:   "WARN",
			expectJSON: false,
			emitDebug:  false,
			emitInfo:   false,
			emitWarn:   true,
			emitError:  true,
		},
		{
			name:       "dev overridden to ERROR",
			env:        "dev",
			logLevel:   "ERROR",
			expectJSON: false,
			emitDebug:  false,
			emitInfo:   false,
			emitWarn:   false,
			emitError:  true,
		},
		{
			name:       "dev with invalid log level falls back to DEBUG",
			env:        "dev",
			logLevel:   "invalid",
			expectJSON: false,
			emitDebug:  true,
			emitInfo:   true,
			emitWarn:   true,
			emitError:  true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			buf := &bytes.Buffer{}
			logger := SetupLogger(tc.env, tc.logLevel, buf)

			// Emit each level
			buf.Reset()
			logger.Debug("debug message")
			debugLogged := buf.Len() > 0
			if debugLogged != tc.emitDebug {
				t.Errorf("Debug log emitted = %v; want %v (output: %q)", debugLogged, tc.emitDebug, buf.String())
			}

			buf.Reset()
			logger.Info("info message")
			infoLogged := buf.Len() > 0
			if infoLogged != tc.emitInfo {
				t.Errorf("Info log emitted = %v; want %v (output: %q)", infoLogged, tc.emitInfo, buf.String())
			}
			if infoLogged {
				verifyFormatting(t, buf.String(), tc.expectJSON, "info message", "INFO")
			}

			buf.Reset()
			logger.Warn("warn message")
			warnLogged := buf.Len() > 0
			if warnLogged != tc.emitWarn {
				t.Errorf("Warn log emitted = %v; want %v (output: %q)", warnLogged, tc.emitWarn, buf.String())
			}
			if warnLogged {
				verifyFormatting(t, buf.String(), tc.expectJSON, "warn message", "WARN")
			}

			buf.Reset()
			logger.Error("error message")
			errorLogged := buf.Len() > 0
			if errorLogged != tc.emitError {
				t.Errorf("Error log emitted = %v; want %v (output: %q)", errorLogged, tc.emitError, buf.String())
			}
			if errorLogged {
				verifyFormatting(t, buf.String(), tc.expectJSON, "error message", "ERROR")
			}
		})
	}
}

func verifyFormatting(t *testing.T, output string, expectJSON bool, expectedMsg, expectedLevel string) {
	t.Helper()
	line := strings.TrimSpace(output)
	if expectJSON {
		var parsed map[string]any
		if err := json.Unmarshal([]byte(line), &parsed); err != nil {
			t.Fatalf("expected valid JSON output, got error: %v, output: %q", err, line)
		}
		if _, ok := parsed["time"]; !ok {
			t.Errorf("expected 'time' key in JSON output: %s", line)
		}
		if lvl, ok := parsed["level"].(string); !ok || lvl != expectedLevel {
			t.Errorf("expected level %q in JSON output, got: %v", expectedLevel, parsed["level"])
		}
		if msg, ok := parsed["msg"].(string); !ok || msg != expectedMsg {
			t.Errorf("expected msg %q in JSON output, got: %v", expectedMsg, parsed["msg"])
		}
	} else {
		// Text format verification: contains level=... and msg=...
		if !strings.Contains(line, "level="+expectedLevel) {
			t.Errorf("expected %q in text output: %s", "level="+expectedLevel, line)
		}
		if !strings.Contains(line, "msg=\""+expectedMsg+"\"") && !strings.Contains(line, "msg="+expectedMsg) {
			t.Errorf("expected msg %q in text output: %s", expectedMsg, line)
		}
	}
}

func TestSetupLogger_NilWriter(t *testing.T) {
	logger := SetupLogger("dev", "", nil)
	if logger == nil {
		t.Fatal("expected non-nil logger when out is nil")
	}
}
