package config

import (
	"strings"
	"testing"
)

func TestLoad_Defaults(t *testing.T) {
	getenv := func(key string) string {
		return ""
	}

	cfg, err := Load(getenv)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Port != "8080" {
		t.Errorf("Port = %q; want %q", cfg.Port, "8080")
	}
	if cfg.Environment != "dev" {
		t.Errorf("Environment = %q; want %q", cfg.Environment, "dev")
	}
	if cfg.LogLevel != "" {
		t.Errorf("LogLevel = %q; want empty string", cfg.LogLevel)
	}
}

func TestLoad_CustomValues(t *testing.T) {
	envMap := map[string]string{
		"PORT":        "9000",
		"ENVIRONMENT": "prod",
		"LOG_LEVEL":   "INFO",
	}
	getenv := func(key string) string {
		return envMap[key]
	}

	cfg, err := Load(getenv)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Port != "9000" {
		t.Errorf("Port = %q; want %q", cfg.Port, "9000")
	}
	if cfg.Environment != "prod" {
		t.Errorf("Environment = %q; want %q", cfg.Environment, "prod")
	}
	if cfg.LogLevel != "INFO" {
		t.Errorf("LogLevel = %q; want %q", cfg.LogLevel, "INFO")
	}
}

func TestLoad_ValidLogLevels(t *testing.T) {
	levels := []string{"DEBUG", "debug", "  Debug ", "INFO", "info", "WARN", "warn", "WARNING", "warning", "ERROR", "error"}
	for _, lvl := range levels {
		t.Run(lvl, func(t *testing.T) {
			getenv := func(key string) string {
				if key == "LOG_LEVEL" {
					return lvl
				}
				return ""
			}
			cfg, err := Load(getenv)
			if err != nil {
				t.Fatalf("unexpected error for LOG_LEVEL %q: %v", lvl, err)
			}
			expected := strings.ToUpper(strings.TrimSpace(lvl))
			if cfg.LogLevel != expected {
				t.Errorf("LogLevel = %q; want %q", cfg.LogLevel, expected)
			}
		})
	}
}

func TestLoad_InvalidLogLevel_NamesVariable(t *testing.T) {
	getenv := func(key string) string {
		if key == "LOG_LEVEL" {
			return "nope"
		}
		return ""
	}

	_, err := Load(getenv)
	if err == nil {
		t.Fatal("expected error for LOG_LEVEL=nope, got nil")
	}

	if !strings.Contains(err.Error(), "LOG_LEVEL") {
		t.Errorf("expected error to name LOG_LEVEL, got %q", err.Error())
	}
}
