package observability

import (
	"context"
	"testing"
)

func TestSetupOTelWithoutEndpointIsNoOp(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
	t.Setenv("OTEL_SDK_DISABLED", "")

	shutdown := SetupOTel(context.Background())
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

func TestSetupOTelDisabledByEnvIsNoOp(t *testing.T) {
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
	t.Setenv("OTEL_SDK_DISABLED", "true")

	if TelemetryEnabled() {
		t.Fatal("telemetry should be disabled by OTEL_SDK_DISABLED")
	}

	shutdown := SetupOTel(context.Background())
	if shutdown == nil {
		t.Fatal("SetupOTel returned a nil shutdown function")
	}
	if err := shutdown(context.Background()); err != nil {
		t.Fatalf("no-op shutdown returned an error: %v", err)
	}

	_, span := Tracer().Start(context.Background(), "smoke")
	if span.IsRecording() {
		t.Error("expected a no-op tracer when OTEL_SDK_DISABLED is truthy")
	}
	span.End()
}

func TestBuildResourceAttributes(t *testing.T) {
	t.Setenv("ENVIRONMENT", "dev")
	t.Setenv("DEPLOY_ID", "abc123")

	attrs := resourceAttributes(t)
	if got := attrs["service.name"]; got != ServiceName {
		t.Errorf("service.name = %q, want %q", got, ServiceName)
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
	for _, attr := range BuildResource().Attributes() {
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

			if got := TelemetryEnabled(); got != tt.want {
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
