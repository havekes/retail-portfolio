package config

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"retail-portfolio/services/mcp-gateway/internal/backend"
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
//   - DATA_PLANE_PATH: path prefix of the backend service-to-service data plane
//     (for example /api/v1/market/data). Optional, defaults to "/api/v1/market/data".
//     Can also be configured via MARKET_DATA_PATH.
//   - PORT: HTTP listen port. Optional, defaults to "8080".
//   - ENVIRONMENT: deployment environment ("prod" or "dev"). Optional, defaults to "dev".
//   - LOG_LEVEL: log level override ("DEBUG", "INFO", "WARN"/"WARNING", "ERROR"). Optional.
//   - MAX_CONCURRENCY: maximum concurrent outbound requests to the backend data
//     plane. Optional, defaults to 10. Must be a positive integer.
//   - SESSION_IDLE_TIMEOUT: duration after which idle MCP sessions are closed.
//     Optional, defaults to 30m. Must be a positive Go duration.
//   - OTEL_EXPORTER_OTLP_ENDPOINT: target URL for OTLP traces export over HTTP.
//     Optional.
//   - OTEL_EXPORTER_OTLP_HEADERS: key=value pairs for OTLP exporter headers.
//     Optional. Header values are never logged or exposed in errors.
//   - OTEL_RESOURCE_ATTRIBUTES: comma-separated key=value attributes for the
//     telemetry resource. Optional.
//   - OTEL_SDK_DISABLED: when truthy ("1", "true", "yes", "on"), disables
//     OpenTelemetry tracing even if an endpoint is configured. Optional.
//   - DEPLOY_ID: identifier of the deployment/release (e.g. dev, git sha). Optional.
type Config struct {
	BackendBaseURL     string
	ServiceToken       string
	DataPlanePath      string
	MarketDataPath     string
	Port               string
	Environment        string
	LogLevel           string
	MaxConcurrency     int
	SessionIdleTimeout time.Duration
	OTLPEndpoint       string
	OTLPHeaders        string
	ResourceAttributes string
	SDKDisabled        bool
	DeployID           string
}

const (
	defaultPort               = "8080"
	defaultEnvironment        = "dev"
	defaultMaxConcurrency     = 10
	defaultSessionIdleTimeout = 30 * time.Minute
	defaultDataPlanePath      = backend.DefaultDataPlanePath
)

// Load reads the gateway configuration from getenv.
//
// getenv is injected (rather than calling os.Getenv directly) so the parsing
// rules are unit-testable without mutating the process environment.
//
// A missing or unusable required value is a startup error: the returned error
// names the offending variable but never echoes the token value.
func Load(getenv func(string) string) (Config, error) {
	env := strings.ToLower(strings.TrimSpace(getenv("ENVIRONMENT")))
	if env == "" {
		env = defaultEnvironment
	}

	logLevel := strings.ToUpper(strings.TrimSpace(getenv("LOG_LEVEL")))
	if logLevel != "" {
		switch logLevel {
		case "DEBUG", "INFO", "WARN", "WARNING", "ERROR":
		default:
			return Config{}, fmt.Errorf("invalid LOG_LEVEL %q: must be DEBUG, INFO, WARN, WARNING, or ERROR", logLevel)
		}
	}

	maxConcurrencyStr := strings.TrimSpace(getenv("MAX_CONCURRENCY"))
	maxConcurrency := defaultMaxConcurrency
	if maxConcurrencyStr != "" {
		val, err := strconv.Atoi(maxConcurrencyStr)
		if err != nil || val <= 0 {
			return Config{}, fmt.Errorf("invalid MAX_CONCURRENCY %q: must be a positive integer", maxConcurrencyStr)
		}
		maxConcurrency = val
	}

	sessionIdleTimeoutStr := strings.TrimSpace(getenv("SESSION_IDLE_TIMEOUT"))
	sessionIdleTimeout := defaultSessionIdleTimeout
	if sessionIdleTimeoutStr != "" {
		val, err := time.ParseDuration(sessionIdleTimeoutStr)
		if err != nil || val <= 0 {
			return Config{}, fmt.Errorf("invalid SESSION_IDLE_TIMEOUT %q: must be a positive duration", sessionIdleTimeoutStr)
		}
		sessionIdleTimeout = val
	}

	rawPath := strings.TrimSpace(getenv("DATA_PLANE_PATH"))
	if rawPath == "" {
		rawPath = strings.TrimSpace(getenv("MARKET_DATA_PATH"))
	}
	dataPlanePath := defaultDataPlanePath
	if rawPath != "" {
		p := strings.TrimRight(rawPath, "/")
		if p != "" && !strings.HasPrefix(p, "/") {
			p = "/" + p
		}
		dataPlanePath = p
	}

	sdkDisabledRaw := strings.ToLower(strings.TrimSpace(getenv("OTEL_SDK_DISABLED")))
	sdkDisabled := false
	switch sdkDisabledRaw {
	case "1", "true", "yes", "on":
		sdkDisabled = true
	}

	cfg := Config{
		BackendBaseURL:     strings.TrimSpace(getenv("BACKEND_BASE_URL")),
		ServiceToken:       strings.TrimSpace(getenv("MARKET_DATA_SERVICE_TOKEN")),
		DataPlanePath:      dataPlanePath,
		MarketDataPath:     dataPlanePath,
		Port:               strings.TrimSpace(getenv("PORT")),
		Environment:        env,
		LogLevel:           logLevel,
		MaxConcurrency:     maxConcurrency,
		SessionIdleTimeout: sessionIdleTimeout,
		OTLPEndpoint:       strings.TrimSpace(getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
		OTLPHeaders:        strings.TrimSpace(getenv("OTEL_EXPORTER_OTLP_HEADERS")),
		ResourceAttributes: strings.TrimSpace(getenv("OTEL_RESOURCE_ATTRIBUTES")),
		SDKDisabled:        sdkDisabled,
		DeployID:           strings.TrimSpace(getenv("DEPLOY_ID")),
	}

	if cfg.BackendBaseURL == "" {
		return Config{}, errors.New("BACKEND_BASE_URL is required")
	}
	if err := backend.ValidateBaseURL(cfg.BackendBaseURL); err != nil {
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

// IsDev reports whether env corresponds to a development environment.
// An empty environment string defaults to "dev" per defaultEnvironment.
func IsDev(env string) bool {
	norm := strings.ToLower(strings.TrimSpace(env))
	if norm == "" {
		norm = defaultEnvironment
	}
	return norm == "dev"
}
