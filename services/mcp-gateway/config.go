package main

import (
	"errors"
	"fmt"
	"net/url"
	"strings"
)

// Config holds the runtime configuration for the MCP gateway.
//
// Every value comes from the environment so the same binary runs unchanged in
// local Compose and in CI:
//
//   - BACKEND_BASE_URL: origin of the backend data plane (for example
//     http://backend:8000). Required.
//   - MARKET_DATA_SERVICE_TOKEN: shared secret sent as X-Service-Token to the
//     backend data-plane endpoints. Required. The value is never logged or
//     embedded in an error message.
//   - PORT: HTTP listen port. Optional, defaults to "8080".
type Config struct {
	BackendBaseURL string
	ServiceToken   string
	Port           string
}

const defaultPort = "8080"

// loadConfig reads the gateway configuration from getenv.
//
// getenv is injected (rather than calling os.Getenv directly) so the parsing
// rules are unit-testable without mutating the process environment.
//
// A missing or unusable required value is a startup error: the returned error
// names the offending variable but never echoes the token value.
func loadConfig(getenv func(string) string) (Config, error) {
	cfg := Config{
		BackendBaseURL: strings.TrimSpace(getenv("BACKEND_BASE_URL")),
		ServiceToken:   strings.TrimSpace(getenv("MARKET_DATA_SERVICE_TOKEN")),
		Port:           strings.TrimSpace(getenv("PORT")),
	}

	if cfg.BackendBaseURL == "" {
		return Config{}, errors.New("BACKEND_BASE_URL is required")
	}
	if err := validateBaseURL(cfg.BackendBaseURL); err != nil {
		return Config{}, fmt.Errorf("BACKEND_BASE_URL is invalid: %w", err)
	}
	if cfg.ServiceToken == "" {
		return Config{}, errors.New("MARKET_DATA_SERVICE_TOKEN is required")
	}
	if cfg.Port == "" {
		cfg.Port = defaultPort
	}

	return cfg, nil
}

// validateBaseURL rejects values that parse but cannot address an HTTP origin
// (for example "not-a-url" or "ftp://host"), so a misconfigured environment
// fails at startup instead of on the first backend call.
func validateBaseURL(raw string) error {
	parsed, err := url.Parse(raw)
	if err != nil {
		return err
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return errors.New("scheme must be http or https")
	}
	if parsed.Host == "" {
		return errors.New("host is required")
	}
	return nil
}
