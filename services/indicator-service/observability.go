package main

import (
	"context"
	"log"
	"os"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

const (
	// serviceName identifies this service in exported telemetry.
	serviceName = "indicator-service"
	// tracerName is the instrumentation scope reported on every span.
	tracerName = "indicator-service"

	// tracesPath is the OTLP/HTTP traces path, appended to the configured
	// endpoint when it is not already present (mirrors the Python bootstrap).
	tracesPath = "/v1/traces"
)

// providerOverride is the tracer provider used for this service's spans.
//
// The OpenTelemetry global provider can only be assigned once per process,
// which makes it unusable for hermetic tests that need a fresh provider per
// case. Spans therefore resolve their tracer through providerOverride when it
// is set (production sets it, tests set it per case) and fall back to the
// global provider otherwise.
var providerOverride trace.TracerProvider

// tracer returns the tracer used for server and handler spans.
func tracer() trace.Tracer {
	if providerOverride != nil {
		return providerOverride.Tracer(tracerName)
	}
	return otel.Tracer(tracerName)
}

// setTracerProvider installs p as this service's tracer provider and returns a
// function restoring the previous value (used by tests for isolation).
func setTracerProvider(p trace.TracerProvider) func() {
	previous := providerOverride
	providerOverride = p
	return func() { providerOverride = previous }
}

// newPropagator returns the global propagator: W3C trace context (so an inbound
// traceparent is continued) plus baggage, mirroring the Python services.
func newPropagator() propagation.TextMapPropagator {
	return propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	)
}

// telemetryEnabled reports whether an OTLP export should be configured.
//
// Export requires an endpoint; OTEL_SDK_DISABLED truthy turns it off.
func telemetryEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("OTEL_SDK_DISABLED"))) {
	case "1", "true", "yes", "on":
		return false
	}
	return strings.TrimSpace(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")) != ""
}

// resolveOTLPEndpoint normalises the configured OTLP/HTTP endpoint to the
// traces URL, matching the Python bootstrap so both services hit the same
// collector path.
func resolveOTLPEndpoint(endpoint string) string {
	resolved := strings.TrimRight(strings.TrimSpace(endpoint), "/")
	if resolved == "" {
		return ""
	}
	if !strings.HasSuffix(resolved, tracesPath) {
		resolved += tracesPath
	}
	return resolved
}

// parseOTLPHeaders parses the comma-separated key=value form of
// OTEL_EXPORTER_OTLP_HEADERS into exporter headers.
func parseOTLPHeaders(raw string) map[string]string {
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

// buildResource builds the telemetry resource for this service.
//
// OTEL_RESOURCE_ATTRIBUTES is merged in by the SDK (WithResource merges
// resource.Environment() with this resource, the explicit attributes winning),
// so only the service-specific attributes are built here.
func buildResource() *resource.Resource {
	attrs := []attribute.KeyValue{
		attribute.String("service.name", serviceName),
	}
	if environment := strings.TrimSpace(os.Getenv("ENVIRONMENT")); environment != "" {
		attrs = append(attrs, attribute.String("deployment.environment", environment))
	}
	if deployID := strings.TrimSpace(os.Getenv("DEPLOY_ID")); deployID != "" {
		attrs = append(attrs, attribute.String("deploy_id", deployID))
	}
	return resource.NewSchemaless(attrs...)
}

// otelOptions carries the hook points tests use to exercise the SDK path.
type otelOptions struct {
	// spanProcessor replaces the OTLP batch processor when non-nil, so tests
	// can assert on recorded spans without dialing a collector.
	spanProcessor sdktrace.SpanProcessor
}

// setupOTel initialises OpenTelemetry for this process.
//
// The W3C propagator is always installed so an inbound traceparent is
// continued. The SDK provider and its OTLP/HTTP exporter are only built when
// an endpoint is configured and OTEL_SDK_DISABLED is not truthy; otherwise the
// process keeps the no-op tracer and no exporter is constructed (a batch
// processor with an empty endpoint would retry in the background).
//
// The returned function flushes and shuts the provider down. It is never nil
// and safe to call on the disabled path.
func setupOTel(ctx context.Context) func(context.Context) error {
	return setupOTelWithOptions(ctx, otelOptions{})
}

// setupOTelWithOptions is setupOTel with test-only injection points.
func setupOTelWithOptions(ctx context.Context, opts otelOptions) func(context.Context) error {
	otel.SetTextMapPropagator(newPropagator())

	injected := opts.spanProcessor != nil
	if !injected {
		if !telemetryEnabled() {
			return func(context.Context) error { return nil }
		}

		exporterOpts := []otlptracehttp.Option{
			otlptracehttp.WithEndpointURL(
				resolveOTLPEndpoint(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
			),
		}
		if headers := parseOTLPHeaders(os.Getenv("OTEL_EXPORTER_OTLP_HEADERS")); len(headers) > 0 {
			exporterOpts = append(exporterOpts, otlptracehttp.WithHeaders(headers))
		}

		exporter, err := otlptracehttp.New(ctx, exporterOpts...)
		if err != nil {
			log.Printf("otel: failed to initialise the OTLP exporter, telemetry disabled: %v\n", err)
			return func(context.Context) error { return nil }
		}
		opts.spanProcessor = sdktrace.NewBatchSpanProcessor(exporter)
	}

	provider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(buildResource()),
		sdktrace.WithSpanProcessor(opts.spanProcessor),
	)
	providerOverride = provider
	if !injected {
		// The global provider can only be assigned once per process; tests
		// inject a processor and rely on providerOverride instead.
		otel.SetTracerProvider(provider)
	}

	return func(shutdownCtx context.Context) error {
		err := provider.Shutdown(shutdownCtx)
		providerOverride = nil
		return err
	}
}
