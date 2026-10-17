package observability

import (
	"context"
	"testing"

	"go.opentelemetry.io/otel/sdk/trace/tracetest"

	"retail-portfolio/services/mcp-gateway/internal/config"
)

func TestSetupOTelWithoutEndpointIsNoOp(t *testing.T) {
	cfg := config.Config{
		OTLPEndpoint: "",
		SDKDisabled:  false,
	}

	shutdown := SetupOTel(context.Background(), cfg)
	if shutdown == nil {
		t.Fatal("SetupOTel returned a nil shutdown function")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("no-op shutdown returned an error: %v", err)
	}

	_, span := Tracer().Start(context.Background(), "smoke")
	if span.IsRecording() {
		t.Error("expected a no-op tracer when no OTLP endpoint is configured")
	}
	span.End()
}

func TestSetupOTelDisabledByConfigIsNoOp(t *testing.T) {
	cfg := config.Config{
		OTLPEndpoint: "http://127.0.0.1:1",
		SDKDisabled:  true,
	}

	if TelemetryEnabled(cfg) {
		t.Fatal("telemetry should be disabled by SDKDisabled")
	}

	shutdown := SetupOTel(context.Background(), cfg)
	if shutdown == nil {
		t.Fatal("SetupOTel returned a nil shutdown function")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("no-op shutdown returned an error: %v", err)
	}

	_, span := Tracer().Start(context.Background(), "smoke")
	if span.IsRecording() {
		t.Error("expected a no-op tracer when SDKDisabled is true")
	}
	span.End()
}

func TestSetupOTelWithInMemoryExporter(t *testing.T) {
	cfg := config.Config{
		Environment: "production",
		DeployID:    "dep-456",
	}

	recorder := tracetest.NewSpanRecorder()
	shutdown := SetupOTelWithOptions(context.Background(), cfg, OTelOptions{
		SpanProcessor: recorder,
	})
	if shutdown == nil {
		t.Fatal("SetupOTelWithOptions returned nil shutdown")
	}

	ctx, span := Tracer().Start(context.Background(), "test-span")
	span.End()

	spans := recorder.Ended()
	if len(spans) != 1 {
		t.Fatalf("expected 1 ended span, got %d", len(spans))
	}

	recorded := spans[0]
	if recorded.Name() != "test-span" {
		t.Errorf("span name = %q, want test-span", recorded.Name())
	}

	resAttrs := map[string]string{}
	for _, attr := range recorded.Resource().Attributes() {
		resAttrs[string(attr.Key)] = attr.Value.AsString()
	}
	if resAttrs["service.name"] != ServiceName {
		t.Errorf("resource service.name = %q, want %q", resAttrs["service.name"], ServiceName)
	}
	if resAttrs["deployment.environment"] != "production" {
		t.Errorf("resource deployment.environment = %q, want production", resAttrs["deployment.environment"])
	}
	if resAttrs["deploy_id"] != "dep-456" {
		t.Errorf("resource deploy_id = %q, want dep-456", resAttrs["deploy_id"])
	}

	// Verify shutdown clears active provider
	if err := shutdown(ctx); err != nil {
		t.Fatalf("shutdown error: %v", err)
	}

	_, postSpan := Tracer().Start(context.Background(), "after-shutdown")
	if postSpan.IsRecording() {
		t.Error("tracer should be no-op after shutdown")
	}
	postSpan.End()
}

func TestBuildResourceAttributes(t *testing.T) {
	cfg := config.Config{
		Environment:        "dev",
		DeployID:           "abc123",
		ResourceAttributes: "k1=v1,k2=v2",
	}

	attrs := resourceAttributes(t, cfg)
	if got := attrs["service.name"]; got != ServiceName {
		t.Errorf("service.name = %q, want %q", got, ServiceName)
	}
	if got := attrs["deployment.environment"]; got != "dev" {
		t.Errorf("deployment.environment = %q, want %q", got, "dev")
	}
	if got := attrs["deploy_id"]; got != "abc123" {
		t.Errorf("deploy_id = %q, want %q", got, "abc123")
	}
	if got := attrs["k1"]; got != "v1" {
		t.Errorf("k1 = %q, want %q", got, "v1")
	}
	if got := attrs["k2"]; got != "v2" {
		t.Errorf("k2 = %q, want %q", got, "v2")
	}
}

func TestBuildResourceOmitsEmptyAttributes(t *testing.T) {
	cfg := config.Config{}

	attrs := resourceAttributes(t, cfg)
	if _, ok := attrs["deployment.environment"]; ok {
		t.Error("deployment.environment should be omitted when Environment is unset")
	}
	if _, ok := attrs["deploy_id"]; ok {
		t.Error("deploy_id should be omitted when DeployID is unset")
	}
}

func resourceAttributes(t *testing.T, cfg config.Config) map[string]string {
	t.Helper()

	attrs := map[string]string{}
	for _, attr := range BuildResource(cfg).Attributes() {
		attrs[string(attr.Key)] = attr.Value.AsString()
	}
	return attrs
}

func TestTelemetryEnabled(t *testing.T) {
	tests := []struct {
		name     string
		endpoint string
		disabled bool
		want     bool
	}{
		{name: "endpoint set", endpoint: "http://clickstack:4318", disabled: false, want: true},
		{name: "no endpoint", endpoint: "", disabled: false, want: false},
		{name: "blank endpoint", endpoint: "   ", disabled: false, want: false},
		{name: "sdk disabled true", endpoint: "http://clickstack:4318", disabled: true, want: false},
		{name: "sdk disabled false", endpoint: "http://clickstack:4318", disabled: false, want: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := config.Config{
				OTLPEndpoint: tt.endpoint,
				SDKDisabled:  tt.disabled,
			}
			if got := TelemetryEnabled(cfg); got != tt.want {
				t.Errorf("TelemetryEnabled() = %v, want %v", got, tt.want)
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
		if got := ResolveOTLPEndpoint(tt.endpoint); got != tt.want {
			t.Errorf("ResolveOTLPEndpoint(%q) = %q, want %q", tt.endpoint, got, tt.want)
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
			got := ParseOTLPHeaders(tt.raw)
			if len(got) != len(tt.want) {
				t.Fatalf("ParseOTLPHeaders(%q) = %v, want %v", tt.raw, got, tt.want)
			}
			for key, value := range tt.want {
				if got[key] != value {
					t.Errorf("ParseOTLPHeaders(%q)[%q] = %q, want %q", tt.raw, key, got[key], value)
				}
			}
		})
	}
}
