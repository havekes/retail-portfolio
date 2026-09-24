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
