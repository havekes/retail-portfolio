package main

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.opentelemetry.io/otel"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
)

// testProvider installs an SDK provider that records spans in memory and
// restores the previous provider when the test ends.
func testProvider(t *testing.T) *tracetest.SpanRecorder {
	t.Helper()

	// Production installs the propagator in setupOTel before serving;
	// tests installing a provider directly do the same.
	otel.SetTextMapPropagator(newPropagator())

	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	restore := setTracerProvider(provider)
	t.Cleanup(func() {
		restore()
		_ = provider.Shutdown(context.Background())
	})
	return recorder
}

func TestSetupOTelWithoutEndpointIsNoOp(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
	t.Setenv("OTEL_SDK_DISABLED", "")

	shutdown := setupOTel(context.Background())
	if shutdown == nil {
		t.Fatal("setupOTel returned a nil shutdown function")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("no-op shutdown returned an error: %v", err)
	}

	_, span := tracer().Start(context.Background(), "smoke")
	if span.IsRecording() {
		t.Error("expected a no-op tracer when no OTLP endpoint is configured")
	}
	span.End()

	// The service still serves normally through the middleware chain.
	assertServesNormally(t)
}

func TestSetupOTelDisabledByEnvIsNoOp(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
	t.Setenv("OTEL_SDK_DISABLED", "true")

	if telemetryEnabled() {
		t.Fatal("telemetry should be disabled by OTEL_SDK_DISABLED")
	}

	shutdown := setupOTel(context.Background())
	if shutdown == nil {
		t.Fatal("setupOTel returned a nil shutdown function")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("no-op shutdown returned an error: %v", err)
	}

	_, span := tracer().Start(context.Background(), "smoke")
	if span.IsRecording() {
		t.Error("expected a no-op tracer when OTEL_SDK_DISABLED is truthy")
	}
	span.End()

	assertServesNormally(t)
}

// assertServesNormally hits the wrapped router the way the service is served.
func assertServesNormally(t *testing.T) {
	t.Helper()

	handler := servedHandler()

	healthRec := httptest.NewRecorder()
	handler.ServeHTTP(healthRec, httptest.NewRequest(http.MethodGet, "/health", nil))
	if healthRec.Code != http.StatusOK {
		t.Fatalf("GET /health = %d, want 200", healthRec.Code)
	}

	computeRec := httptest.NewRecorder()
	handler.ServeHTTP(
		computeRec,
		httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(computeRequestBody(t, 3, 1))),
	)
	if computeRec.Code != http.StatusOK {
		t.Fatalf("POST /compute = %d, want 200: %s", computeRec.Code, computeRec.Body.String())
	}
}

func TestSetupOTelWithStubProcessorRecordsSpans(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	shutdown := setupOTelWithOptions(context.Background(), otelOptions{spanProcessor: recorder})
	t.Cleanup(func() {
		if err := shutdown(context.Background()); err != nil {
			t.Errorf("shutdown returned an error: %v", err)
		}
	})

	assertServesNormally(t)

	if got := len(recorder.Ended()); got != 3 {
		t.Fatalf("expected 3 spans (health plus compute server and handler spans) recorded, got %d", got)
	}
}

func TestBuildResourceAttributes(t *testing.T) {
	t.Setenv("ENVIRONMENT", "dev")
	t.Setenv("DEPLOY_ID", "abc123")

	attrs := resourceAttributes(t)
	if got := attrs["service.name"]; got != serviceName {
		t.Errorf("service.name = %q, want %q", got, serviceName)
	}
	if got := attrs["deployment.environment"]; got != "dev" {
		t.Errorf("deployment.environment = %q, want %q", got, "dev")
	}
	if got := attrs["deploy_id"]; got != "abc123" {
		t.Errorf("deploy_id = %q, want %q", got, "abc123")
	}
}

func TestBuildResourceOmitsEmptyAttributes(t *testing.T) {
	t.Setenv("ENVIRONMENT", "")
	t.Setenv("DEPLOY_ID", "")

	attrs := resourceAttributes(t)
	if _, ok := attrs["deployment.environment"]; ok {
		t.Error("deployment.environment should be omitted when ENVIRONMENT is unset")
	}
	if _, ok := attrs["deploy_id"]; ok {
		t.Error("deploy_id should be omitted when DEPLOY_ID is unset")
	}
}

func resourceAttributes(t *testing.T) map[string]string {
	t.Helper()

	attrs := map[string]string{}
	for _, attr := range buildResource().Attributes() {
		attrs[string(attr.Key)] = attr.Value.Emit()
	}
	return attrs
}

func TestTelemetryEnabled(t *testing.T) {
	tests := []struct {
		name     string
		endpoint string
		disabled string
		want     bool
	}{
		{name: "endpoint set", endpoint: "http://clickstack:4318", disabled: "", want: true},
		{name: "no endpoint", endpoint: "", disabled: "", want: false},
		{name: "blank endpoint", endpoint: "   ", disabled: "", want: false},
		{name: "sdk disabled true", endpoint: "http://clickstack:4318", disabled: "true", want: false},
		{name: "sdk disabled 1", endpoint: "http://clickstack:4318", disabled: "1", want: false},
		{name: "sdk disabled false", endpoint: "http://clickstack:4318", disabled: "false", want: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", tt.endpoint)
			t.Setenv("OTEL_SDK_DISABLED", tt.disabled)

			if got := telemetryEnabled(); got != tt.want {
				t.Errorf("telemetryEnabled() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestResolveOTLPEndpoint(t *testing.T) {
	tests := []struct {
		endpoint string
		want     string
	}{
		{endpoint: "", want: ""},
		{endpoint: "   ", want: ""},
		{endpoint: "http://clickstack:4318", want: "http://clickstack:4318/v1/traces"},
		{endpoint: "http://clickstack:4318/", want: "http://clickstack:4318/v1/traces"},
		{endpoint: "http://clickstack:4318/v1/traces", want: "http://clickstack:4318/v1/traces"},
	}

	for _, tt := range tests {
		if got := resolveOTLPEndpoint(tt.endpoint); got != tt.want {
			t.Errorf("resolveOTLPEndpoint(%q) = %q, want %q", tt.endpoint, got, tt.want)
		}
	}
}

func TestParseOTLPHeaders(t *testing.T) {
	tests := []struct {
		name string
		raw  string
		want map[string]string
	}{
		{name: "empty", raw: "", want: map[string]string{}},
		{
			name: "single header",
			raw:  "authorization=abc123",
			want: map[string]string{"authorization": "abc123"},
		},
		{
			name: "multiple headers, spaced and keep first delimiter",
			raw:  " authorization = abc123 ,x-tenant=acme=1, malformed ",
			want: map[string]string{"authorization": "abc123", "x-tenant": "acme=1"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseOTLPHeaders(tt.raw)
			if len(got) != len(tt.want) {
				t.Fatalf("parseOTLPHeaders(%q) = %v, want %v", tt.raw, got, tt.want)
			}
			for key, value := range tt.want {
				if got[key] != value {
					t.Errorf("parseOTLPHeaders(%q)[%q] = %q, want %q", tt.raw, key, got[key], value)
				}
			}
		})
	}
}
