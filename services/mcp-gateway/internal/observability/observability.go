package observability

import (
	"context"
	"log"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
	"go.opentelemetry.io/otel/trace/noop"

	"retail-portfolio/services/mcp-gateway/internal/config"
)

const (
	// ServiceName identifies this service in exported telemetry.
	ServiceName = "mcp-gateway"
	// TracerName is the instrumentation scope reported on every span.
	TracerName = "mcp-gateway"

	// tracesPath is the OTLP/HTTP traces path, appended to the configured
	// endpoint when it is not already present (mirrors the Python bootstrap).
	tracesPath = "/v1/traces"
)

// providerOverride is the tracer provider used for this service's spans.
//
// The OpenTelemetry global provider can only be assigned once per process in
// earlier SDKs, but tests also need per-test isolation. Spans therefore resolve
// their tracer through providerOverride when set and fall back to the global
// provider otherwise.
var providerOverride trace.TracerProvider

// Tracer returns the tracer used for server and handler spans.
func Tracer() trace.Tracer {
	if providerOverride != nil {
		return providerOverride.Tracer(TracerName)
	}
	return otel.Tracer(TracerName)
}

// SetTracerProvider installs p as this service's tracer provider and returns a
// function restoring the previous value (used by tests for isolation).
func SetTracerProvider(p trace.TracerProvider) func() {
	previous := providerOverride
	providerOverride = p
	otel.SetTracerProvider(p)
	return func() {
		providerOverride = previous
		if previous != nil {
			otel.SetTracerProvider(previous)
		} else {
			otel.SetTracerProvider(noop.NewTracerProvider())
		}
	}
}

// NewPropagator returns the global propagator: W3C trace context (so an inbound
// traceparent is continued) plus baggage, mirroring the Python services.
func NewPropagator() propagation.TextMapPropagator {
	return propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	)
}

// TelemetryEnabled reports whether an OTLP export should be configured.
//
// Export requires an endpoint; SDKDisabled truthy turns it off.
func TelemetryEnabled(cfg config.Config) bool {
	if cfg.SDKDisabled {
		return false
	}
	return strings.TrimSpace(cfg.OTLPEndpoint) != ""
}

// ResolveOTLPEndpoint normalises the configured OTLP/HTTP endpoint to the
// traces URL, matching the Python bootstrap so all services hit the same
// collector path.
func ResolveOTLPEndpoint(endpoint string) string {
	resolved := strings.TrimRight(strings.TrimSpace(endpoint), "/")
	if resolved == "" {
		return ""
	}
	if !strings.HasSuffix(resolved, tracesPath) {
		resolved += tracesPath
	}
	return resolved
}

// ParseOTLPHeaders parses the comma-separated key=value form of
// OTEL_EXPORTER_OTLP_HEADERS into exporter headers.
func ParseOTLPHeaders(raw string) map[string]string {
	headers := map[string]string{}
	if strings.TrimSpace(raw) == "" {
		return headers
	}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		key, value, found := strings.Cut(part, "=")
		key = strings.TrimSpace(key)
		if !found || key == "" {
			continue
		}
		headers[key] = strings.TrimSpace(value)
	}
	return headers
}

// BuildResource builds the telemetry resource for this service.
func BuildResource(cfg config.Config) *resource.Resource {
	attrs := []attribute.KeyValue{
		attribute.String("service.name", ServiceName),
	}
	if environment := strings.TrimSpace(cfg.Environment); environment != "" {
		attrs = append(attrs, attribute.String("deployment.environment", environment))
	}
	if deployID := strings.TrimSpace(cfg.DeployID); deployID != "" {
		attrs = append(attrs, attribute.String("deploy_id", deployID))
	}
	if rawAttrs := strings.TrimSpace(cfg.ResourceAttributes); rawAttrs != "" {
		for _, part := range strings.Split(rawAttrs, ",") {
			part = strings.TrimSpace(part)
			if part == "" {
				continue
			}
			key, value, found := strings.Cut(part, "=")
			key = strings.TrimSpace(key)
			if !found || key == "" {
				continue
			}
			attrs = append(attrs, attribute.String(key, strings.TrimSpace(value)))
		}
	}
	return resource.NewSchemaless(attrs...)
}

// OTelOptions carries the hook points tests use to exercise the SDK path.
type OTelOptions struct {
	// SpanProcessor replaces the OTLP batch processor when non-nil, so tests
	// can assert on recorded spans without dialing a collector.
	SpanProcessor sdktrace.SpanProcessor
}

// SetupOTel initialises OpenTelemetry for this process.
//
// The W3C propagator is always installed so an inbound traceparent is
// continued. The SDK provider and its OTLP/HTTP exporter are only built when
// an endpoint is configured and SDKDisabled is false; otherwise the
// process keeps the no-op tracer and no exporter is constructed (a batch
// processor with an empty endpoint would retry in the background).
//
// The returned function flushes and shuts the provider down. It is never nil
// and safe to call on the disabled path.
func SetupOTel(ctx context.Context, cfg config.Config) func(context.Context) error {
	return SetupOTelWithOptions(ctx, cfg, OTelOptions{})
}

// SetupOTelWithOptions is SetupOTel with test-only injection points.
func SetupOTelWithOptions(ctx context.Context, cfg config.Config, opts OTelOptions) func(context.Context) error {
	otel.SetTextMapPropagator(NewPropagator())

	injected := opts.SpanProcessor != nil
	if !injected {
		if !TelemetryEnabled(cfg) {
			return func(context.Context) error { return nil }
		}

		exporterOpts := []otlptracehttp.Option{
			otlptracehttp.WithEndpointURL(
				ResolveOTLPEndpoint(cfg.OTLPEndpoint),
			),
		}
		if headers := ParseOTLPHeaders(cfg.OTLPHeaders); len(headers) > 0 {
			exporterOpts = append(exporterOpts, otlptracehttp.WithHeaders(headers))
		}

		exporter, err := otlptracehttp.New(ctx, exporterOpts...)
		if err != nil {
			log.Printf("otel: failed to initialise the OTLP exporter, telemetry disabled: %v\n", err)
			return func(context.Context) error { return nil }
		}
		opts.SpanProcessor = sdktrace.NewBatchSpanProcessor(exporter)
	}

	provider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(BuildResource(cfg)),
		sdktrace.WithSpanProcessor(opts.SpanProcessor),
	)
	providerOverride = provider
	otel.SetTracerProvider(provider)

	return func(shutdownCtx context.Context) error {
		err := provider.Shutdown(shutdownCtx)
		providerOverride = nil
		otel.SetTracerProvider(noop.NewTracerProvider())
		return err
	}
}
