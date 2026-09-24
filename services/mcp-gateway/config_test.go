package main

import (
	"strings"
	"testing"
)

// envMap turns a map into the injected getenv function.
func envMap(values map[string]string) func(string) string {
	return func(key string) string { return values[key] }
}

func TestLoadConfig(t *testing.T) {
	t.Run("valid configuration", func(t *testing.T) {
		cfg, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL":          "http://backend:8000",
			"MARKET_DATA_SERVICE_TOKEN": "test-token",
			"PORT":                      "9090",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.BackendBaseURL != "http://backend:8000" {
			t.Errorf("BackendBaseURL = %q", cfg.BackendBaseURL)
		}
		if cfg.ServiceToken != "test-token" {
			t.Errorf("ServiceToken = %q", cfg.ServiceToken)
		}
		if cfg.Port != "9090" {
			t.Errorf("Port = %q", cfg.Port)
		}
		if cfg.Environment != "dev" {
			t.Errorf("Environment = %q, want %q", cfg.Environment, "dev")
		}
		if cfg.LogLevel != "" {
			t.Errorf("LogLevel = %q, want empty", cfg.LogLevel)
		}
	})

	t.Run("environment default dev when unset or whitespace", func(t *testing.T) {
		for _, envVal := range []string{"", "   "} {
			cfg, err := loadConfig(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"ENVIRONMENT":               envVal,
			}))
			if err != nil {
				t.Fatalf("unexpected error for ENVIRONMENT=%q: %v", envVal, err)
			}
			if cfg.Environment != "dev" {
				t.Errorf("Environment = %q, want %q", cfg.Environment, "dev")
			}
		}
	})

	t.Run("environment parsed for prod and dev", func(t *testing.T) {
		cases := []struct {
			input string
			want  string
		}{
			{"prod", "prod"},
			{"PROD", "prod"},
			{"  prod  ", "prod"},
			{"dev", "dev"},
			{"DEV", "dev"},
			{"  dev  ", "dev"},
		}
		for _, tc := range cases {
			cfg, err := loadConfig(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"ENVIRONMENT":               tc.input,
			}))
			if err != nil {
				t.Fatalf("unexpected error for ENVIRONMENT=%q: %v", tc.input, err)
			}
			if cfg.Environment != tc.want {
				t.Errorf("ENVIRONMENT %q: got %q, want %q", tc.input, cfg.Environment, tc.want)
			}
		}
	})

	t.Run("valid LOG_LEVEL values", func(t *testing.T) {
		cases := []struct {
			input string
			want  string
		}{
			{"DEBUG", "DEBUG"},
			{"debug", "DEBUG"},
			{"  debug  ", "DEBUG"},
			{"INFO", "INFO"},
			{"info", "INFO"},
			{"WARN", "WARN"},
			{"warn", "WARN"},
			{"WARNING", "WARNING"},
			{"warning", "WARNING"},
			{"ERROR", "ERROR"},
			{"error", "ERROR"},
		}
		for _, tc := range cases {
			cfg, err := loadConfig(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"LOG_LEVEL":                 tc.input,
			}))
			if err != nil {
				t.Fatalf("unexpected error for LOG_LEVEL=%q: %v", tc.input, err)
			}
			if cfg.LogLevel != tc.want {
				t.Errorf("LOG_LEVEL %q: got %q, want %q", tc.input, cfg.LogLevel, tc.want)
			}
		}
	})

	t.Run("invalid LOG_LEVEL returns error", func(t *testing.T) {
		const token = "secret-token-123"
		cfg, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL":          "http://backend:8000",
			"MARKET_DATA_SERVICE_TOKEN": token,
			"LOG_LEVEL":                 "INVALID",
		}))
		if err == nil {
			t.Fatalf("expected error for invalid LOG_LEVEL, got cfg: %+v", cfg)
		}
		if !strings.Contains(err.Error(), "LOG_LEVEL") {
			t.Errorf("error %q does not mention LOG_LEVEL", err)
		}
		if strings.Contains(err.Error(), token) {
			t.Errorf("error leaked the token: %q", err)
		}
	})

	t.Run("port defaults to 8080", func(t *testing.T) {
		cfg, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL":          "https://backend.example",
			"MARKET_DATA_SERVICE_TOKEN": "test-token",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.Port != defaultPort {
			t.Errorf("Port = %q, want %q", cfg.Port, defaultPort)
		}
	})

	t.Run("missing backend base url", func(t *testing.T) {
		_, err := loadConfig(envMap(map[string]string{
			"MARKET_DATA_SERVICE_TOKEN": "test-token",
		}))
		if err == nil {
			t.Fatal("expected an error")
		}
		if !strings.Contains(err.Error(), "BACKEND_BASE_URL") {
			t.Errorf("error %q does not name BACKEND_BASE_URL", err)
		}
	})

	t.Run("missing service token", func(t *testing.T) {
		_, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL": "http://backend:8000",
		}))
		if err == nil {
			t.Fatal("expected an error")
		}
		if !strings.Contains(err.Error(), "MARKET_DATA_SERVICE_TOKEN") {
			t.Errorf("error %q does not name MARKET_DATA_SERVICE_TOKEN", err)
		}
	})

	t.Run("blank values are missing", func(t *testing.T) {
		_, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL":          "   ",
			"MARKET_DATA_SERVICE_TOKEN": "   ",
		}))
		if err == nil {
			t.Fatal("expected an error")
		}
		if !strings.Contains(err.Error(), "BACKEND_BASE_URL") {
			t.Errorf("error %q does not name BACKEND_BASE_URL", err)
		}
	})

	t.Run("malformed backend base url", func(t *testing.T) {
		for _, raw := range []string{"not-a-url", "ftp://backend:8000", "http://"} {
			_, err := loadConfig(envMap(map[string]string{
				"BACKEND_BASE_URL":          raw,
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
			}))
			if err == nil {
				t.Fatalf("expected an error for %q", raw)
			}
			if !strings.Contains(err.Error(), "BACKEND_BASE_URL") {
				t.Errorf("error %q does not name BACKEND_BASE_URL", err)
			}
		}
	})

	t.Run("error never contains the token", func(t *testing.T) {
		const token = "super-secret-token"
		_, err := loadConfig(envMap(map[string]string{
			"BACKEND_BASE_URL":          "not-a-url",
			"MARKET_DATA_SERVICE_TOKEN": token,
		}))
		if err == nil {
			t.Fatal("expected an error")
		}
		if strings.Contains(err.Error(), token) {
			t.Errorf("error leaked the token: %q", err)
		}
	})
}

func TestIsDev(t *testing.T) {
	cases := []struct {
		env      string
		expected bool
	}{
		{"dev", true},
		{"DEV", true},
		{"  dev  ", true},
		{"", true},
		{"   ", true},
		{"prod", false},
		{"PROD", false},
		{"production", false},
		{"staging", false},
		{"test", false},
	}

	for _, tc := range cases {
		t.Run("env_"+tc.env, func(t *testing.T) {
			got := isDev(tc.env)
			if got != tc.expected {
				t.Errorf("isDev(%q) = %v, want %v", tc.env, got, tc.expected)
			}
		})
	}
}
