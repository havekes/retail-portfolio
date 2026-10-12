package config

import (
	"strings"
	"testing"
	"time"
)

// envMap turns a map into the injected getenv function.
func envMap(values map[string]string) func(string) string {
	return func(key string) string { return values[key] }
}

func TestLoadConfig(t *testing.T) {
	t.Run("valid configuration", func(t *testing.T) {
		cfg, err := Load(envMap(map[string]string{
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
		if cfg.MaxConcurrency != defaultMaxConcurrency {
			t.Errorf("MaxConcurrency = %d, want %d", cfg.MaxConcurrency, defaultMaxConcurrency)
		}
		if cfg.SessionIdleTimeout != defaultSessionIdleTimeout {
			t.Errorf("SessionIdleTimeout = %v, want %v", cfg.SessionIdleTimeout, defaultSessionIdleTimeout)
		}
		if cfg.DataPlanePath != defaultDataPlanePath {
			t.Errorf("DataPlanePath = %q, want %q", cfg.DataPlanePath, defaultDataPlanePath)
		}
		if cfg.MarketDataPath != defaultDataPlanePath {
			t.Errorf("MarketDataPath = %q, want %q", cfg.MarketDataPath, defaultDataPlanePath)
		}
	})

	t.Run("data plane path default when unset or whitespace", func(t *testing.T) {
		for _, pathVal := range []string{"", "   "} {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"DATA_PLANE_PATH":           pathVal,
			}))
			if err != nil {
				t.Fatalf("unexpected error for DATA_PLANE_PATH=%q: %v", pathVal, err)
			}
			if cfg.DataPlanePath != defaultDataPlanePath {
				t.Errorf("DataPlanePath for %q = %q, want %q", pathVal, cfg.DataPlanePath, defaultDataPlanePath)
			}
			if cfg.MarketDataPath != defaultDataPlanePath {
				t.Errorf("MarketDataPath for %q = %q, want %q", pathVal, cfg.MarketDataPath, defaultDataPlanePath)
			}
		}
	})

	t.Run("data plane path override via DATA_PLANE_PATH", func(t *testing.T) {
		cases := []struct {
			input string
			want  string
		}{
			{"/api/v2/market/data", "/api/v2/market/data"},
			{"api/v2/market/data", "/api/v2/market/data"},
			{"/api/v2/market/data/", "/api/v2/market/data"},
			{"api/v2/market/data/", "/api/v2/market/data"},
			{"  /custom/prefix  ", "/custom/prefix"},
			{"/", ""},
		}
		for _, tc := range cases {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"DATA_PLANE_PATH":           tc.input,
			}))
			if err != nil {
				t.Fatalf("unexpected error for DATA_PLANE_PATH=%q: %v", tc.input, err)
			}
			if cfg.DataPlanePath != tc.want {
				t.Errorf("DATA_PLANE_PATH %q: got %q, want %q", tc.input, cfg.DataPlanePath, tc.want)
			}
			if cfg.MarketDataPath != tc.want {
				t.Errorf("MarketDataPath %q: got %q, want %q", tc.input, cfg.MarketDataPath, tc.want)
			}
		}
	})

	t.Run("data plane path override via MARKET_DATA_PATH", func(t *testing.T) {
		cfg, err := Load(envMap(map[string]string{
			"BACKEND_BASE_URL":          "http://backend:8000",
			"MARKET_DATA_SERVICE_TOKEN": "test-token",
			"MARKET_DATA_PATH":          "/alt/data/path",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.DataPlanePath != "/alt/data/path" {
			t.Errorf("DataPlanePath = %q, want %q", cfg.DataPlanePath, "/alt/data/path")
		}
		if cfg.MarketDataPath != "/alt/data/path" {
			t.Errorf("MarketDataPath = %q, want %q", cfg.MarketDataPath, "/alt/data/path")
		}
	})

	t.Run("DATA_PLANE_PATH takes precedence over MARKET_DATA_PATH", func(t *testing.T) {
		cfg, err := Load(envMap(map[string]string{
			"BACKEND_BASE_URL":          "http://backend:8000",
			"MARKET_DATA_SERVICE_TOKEN": "test-token",
			"DATA_PLANE_PATH":           "/primary/path",
			"MARKET_DATA_PATH":          "/secondary/path",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.DataPlanePath != "/primary/path" {
			t.Errorf("DataPlanePath = %q, want %q", cfg.DataPlanePath, "/primary/path")
		}
		if cfg.MarketDataPath != "/primary/path" {
			t.Errorf("MarketDataPath = %q, want %q", cfg.MarketDataPath, "/primary/path")
		}
	})

	t.Run("environment default dev when unset or whitespace", func(t *testing.T) {
		for _, envVal := range []string{"", "   "} {
			cfg, err := Load(envMap(map[string]string{
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
			cfg, err := Load(envMap(map[string]string{
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
			cfg, err := Load(envMap(map[string]string{
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
		cfg, err := Load(envMap(map[string]string{
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

	t.Run("MAX_CONCURRENCY default when unset or whitespace", func(t *testing.T) {
		for _, val := range []string{"", "   "} {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"MAX_CONCURRENCY":           val,
			}))
			if err != nil {
				t.Fatalf("unexpected error for MAX_CONCURRENCY=%q: %v", val, err)
			}
			if cfg.MaxConcurrency != defaultMaxConcurrency {
				t.Errorf("MaxConcurrency for %q = %d, want %d", val, cfg.MaxConcurrency, defaultMaxConcurrency)
			}
		}
	})

	t.Run("valid MAX_CONCURRENCY values", func(t *testing.T) {
		cases := []struct {
			input string
			want  int
		}{
			{"1", 1},
			{"5", 5},
			{"50", 50},
			{" 25 ", 25},
		}
		for _, tc := range cases {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"MAX_CONCURRENCY":           tc.input,
			}))
			if err != nil {
				t.Fatalf("unexpected error for MAX_CONCURRENCY=%q: %v", tc.input, err)
			}
			if cfg.MaxConcurrency != tc.want {
				t.Errorf("MAX_CONCURRENCY %q: got %d, want %d", tc.input, cfg.MaxConcurrency, tc.want)
			}
		}
	})

	t.Run("invalid MAX_CONCURRENCY returns error", func(t *testing.T) {
		const token = "secret-token-123"
		invalidVals := []string{"0", "-1", "-10", "abc", "1.5"}
		for _, val := range invalidVals {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": token,
				"MAX_CONCURRENCY":           val,
			}))
			if err == nil {
				t.Fatalf("expected error for MAX_CONCURRENCY=%q, got cfg: %+v", val, cfg)
			}
			if !strings.Contains(err.Error(), "MAX_CONCURRENCY") {
				t.Errorf("error %q does not mention MAX_CONCURRENCY", err)
			}
			if strings.Contains(err.Error(), token) {
				t.Errorf("error leaked the token: %q", err)
			}
		}
	})

	t.Run("SESSION_IDLE_TIMEOUT default when unset or whitespace", func(t *testing.T) {
		for _, val := range []string{"", "   "} {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"SESSION_IDLE_TIMEOUT":      val,
			}))
			if err != nil {
				t.Fatalf("unexpected error for SESSION_IDLE_TIMEOUT=%q: %v", val, err)
			}
			if cfg.SessionIdleTimeout != defaultSessionIdleTimeout {
				t.Errorf("SessionIdleTimeout for %q = %v, want %v", val, cfg.SessionIdleTimeout, defaultSessionIdleTimeout)
			}
		}
	})

	t.Run("valid SESSION_IDLE_TIMEOUT values", func(t *testing.T) {
		cases := []struct {
			input string
			want  time.Duration
		}{
			{"5m", 5 * time.Minute},
			{" 5m ", 5 * time.Minute},
			{"30s", 30 * time.Second},
			{"1h", 1 * time.Hour},
			{"30m", 30 * time.Minute},
		}
		for _, tc := range cases {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"SESSION_IDLE_TIMEOUT":      tc.input,
			}))
			if err != nil {
				t.Fatalf("unexpected error for SESSION_IDLE_TIMEOUT=%q: %v", tc.input, err)
			}
			if cfg.SessionIdleTimeout != tc.want {
				t.Errorf("SESSION_IDLE_TIMEOUT %q: got %v, want %v", tc.input, cfg.SessionIdleTimeout, tc.want)
			}
		}
	})

	t.Run("invalid SESSION_IDLE_TIMEOUT returns error", func(t *testing.T) {
		const token = "secret-token-123"
		invalidVals := []string{"0", "-1s", "abc", "-5m", "1.5"}
		for _, val := range invalidVals {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": token,
				"SESSION_IDLE_TIMEOUT":      val,
			}))
			if err == nil {
				t.Fatalf("expected error for SESSION_IDLE_TIMEOUT=%q, got cfg: %+v", val, cfg)
			}
			if !strings.Contains(err.Error(), "SESSION_IDLE_TIMEOUT") {
				t.Errorf("error %q does not mention SESSION_IDLE_TIMEOUT", err)
			}
			if strings.Contains(err.Error(), token) {
				t.Errorf("error leaked the token: %q", err)
			}
		}
	})

	t.Run("port defaults to 8080", func(t *testing.T) {
		cfg, err := Load(envMap(map[string]string{
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
		_, err := Load(envMap(map[string]string{
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
		_, err := Load(envMap(map[string]string{
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
		_, err := Load(envMap(map[string]string{
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
			_, err := Load(envMap(map[string]string{
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
		_, err := Load(envMap(map[string]string{
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

	t.Run("otel environment variables parsed correctly", func(t *testing.T) {
		cfg, err := Load(envMap(map[string]string{
			"BACKEND_BASE_URL":            "http://backend:8000",
			"MARKET_DATA_SERVICE_TOKEN":   "test-token",
			"OTEL_EXPORTER_OTLP_ENDPOINT": "http://clickstack:4318",
			"OTEL_EXPORTER_OTLP_HEADERS":  "authorization=secret-otlp-token,x-tenant=test",
			"OTEL_RESOURCE_ATTRIBUTES":    "service.version=1.0.0,region=us-east-1",
			"DEPLOY_ID":                   "deploy-1234",
		}))
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if cfg.OTLPEndpoint != "http://clickstack:4318" {
			t.Errorf("OTLPEndpoint = %q, want %q", cfg.OTLPEndpoint, "http://clickstack:4318")
		}
		if cfg.OTLPHeaders != "authorization=secret-otlp-token,x-tenant=test" {
			t.Errorf("OTLPHeaders = %q, want %q", cfg.OTLPHeaders, "authorization=secret-otlp-token,x-tenant=test")
		}
		if cfg.ResourceAttributes != "service.version=1.0.0,region=us-east-1" {
			t.Errorf("ResourceAttributes = %q, want %q", cfg.ResourceAttributes, "service.version=1.0.0,region=us-east-1")
		}
		if cfg.DeployID != "deploy-1234" {
			t.Errorf("DeployID = %q, want %q", cfg.DeployID, "deploy-1234")
		}
	})

	t.Run("otel sdk disabled toggle", func(t *testing.T) {
		cases := []struct {
			val  string
			want bool
		}{
			{"true", true},
			{"1", true},
			{"yes", true},
			{"on", true},
			{"TRUE", true},
			{" YES ", true},
			{"false", false},
			{"0", false},
			{"no", false},
			{"off", false},
			{"", false},
			{"   ", false},
			{"other", false},
		}
		for _, tc := range cases {
			cfg, err := Load(envMap(map[string]string{
				"BACKEND_BASE_URL":          "http://backend:8000",
				"MARKET_DATA_SERVICE_TOKEN": "test-token",
				"OTEL_SDK_DISABLED":         tc.val,
			}))
			if err != nil {
				t.Fatalf("unexpected error for OTEL_SDK_DISABLED=%q: %v", tc.val, err)
			}
			if cfg.SDKDisabled != tc.want {
				t.Errorf("OTEL_SDK_DISABLED=%q: got %v, want %v", tc.val, cfg.SDKDisabled, tc.want)
			}
		}
	})

	t.Run("error never contains otlp headers", func(t *testing.T) {
		const otlpSecret = "super-secret-otlp-api-key"
		_, err := Load(envMap(map[string]string{
			"BACKEND_BASE_URL":           "not-a-url",
			"MARKET_DATA_SERVICE_TOKEN":  "test-token",
			"OTEL_EXPORTER_OTLP_HEADERS": "authorization=" + otlpSecret,
		}))
		if err == nil {
			t.Fatal("expected an error")
		}
		if strings.Contains(err.Error(), otlpSecret) {
			t.Errorf("error leaked the otlp header value: %q", err)
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
			got := IsDev(tc.env)
			if got != tc.expected {
				t.Errorf("IsDev(%q) = %v, want %v", tc.env, got, tc.expected)
			}
		})
	}
}
