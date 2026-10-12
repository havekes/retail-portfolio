package logging

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"
)

type flusherRecorder struct {
	*httptest.ResponseRecorder
	flushed bool
}

func (f *flusherRecorder) Flush() {
	f.flushed = true
}

func TestLoggingResponseWriter_BasicsAndFlusher(t *testing.T) {
	rec := &flusherRecorder{
		ResponseRecorder: httptest.NewRecorder(),
	}
	lrw := newLoggingResponseWriter(rec)

	if lrw.statusCode != http.StatusOK {
		t.Fatalf("expected initial status 200, got %d", lrw.statusCode)
	}
	if lrw.Unwrap() != rec {
		t.Fatalf("expected Unwrap to return underlying writer")
	}

	lrw.WriteHeader(http.StatusTeapot)
	if lrw.statusCode != http.StatusTeapot {
		t.Fatalf("expected status %d, got %d", http.StatusTeapot, lrw.statusCode)
	}

	// Secondary WriteHeader should not overwrite statusCode
	lrw.WriteHeader(http.StatusOK)
	if lrw.statusCode != http.StatusTeapot {
		t.Fatalf("expected status to remain %d, got %d", http.StatusTeapot, lrw.statusCode)
	}

	n, err := lrw.Write([]byte("test payload"))
	if err != nil || n != 12 {
		t.Fatalf("unexpected Write result: n=%d, err=%v", n, err)
	}
	if lrw.bytesWritten != 12 {
		t.Fatalf("expected 12 bytes written, got %d", lrw.bytesWritten)
	}

	lrw.Flush()
	if !rec.flushed {
		t.Fatalf("expected underlying flusher to be called")
	}
}

func TestLoggingResponseWriter_NonFlusher(t *testing.T) {
	// A plain struct that does not implement http.Flusher
	rec := httptest.NewRecorder()
	lrw := newLoggingResponseWriter(rec)
	// Calling Flush should not panic when underlying writer is not a Flusher
	lrw.Flush()
}

func TestLoggingMiddleware_InboundRequests(t *testing.T) {
	paths := []string{"/health", "/mcp"}

	for _, path := range paths {
		t.Run("path_"+path, func(t *testing.T) {
			var buf bytes.Buffer
			logger, err := New(&buf, "prod", "INFO")
			if err != nil {
				t.Fatalf("newLogger error: %v", err)
			}
			prev := setSlogDefault(logger)
			defer setSlogDefault(prev)

			router := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			})
			handler := Middleware(router, "prod")

			req := httptest.NewRequest(http.MethodGet, path, nil)
			req.RemoteAddr = "192.168.1.100:12345"
			rec := httptest.NewRecorder()

			handler.ServeHTTP(rec, req)

			out := buf.String()
			if out == "" {
				t.Fatalf("expected log output for %s, got empty", path)
			}

			var entry map[string]any
			for _, line := range strings.Split(strings.TrimSpace(out), "\n") {
				var parsed map[string]any
				if err := json.Unmarshal([]byte(line), &parsed); err == nil {
					if parsed["msg"] == "http request" {
						entry = parsed
						break
					}
				}
			}

			if entry == nil {
				t.Fatalf("expected 'http request' log entry for %s, got:\n%s", path, out)
			}

			if entry["method"] != http.MethodGet {
				t.Errorf("expected method GET, got %v", entry["method"])
			}
			if entry["path"] != path {
				t.Errorf("expected path %s, got %v", path, entry["path"])
			}
			if entry["remote_addr"] != "192.168.1.100:12345" {
				t.Errorf("expected remote_addr 192.168.1.100:12345, got %v", entry["remote_addr"])
			}
			if _, ok := entry["status"]; !ok {
				t.Errorf("expected status in log entry, got %v", entry)
			}
			if _, ok := entry["duration"]; !ok {
				t.Errorf("expected duration in log entry, got %v", entry)
			}
		})
	}
}

func TestLoggingMiddleware_DevAndRedaction(t *testing.T) {
	t.Run("dev logs details with redacted sensitive headers", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := New(&buf, "dev", "DEBUG")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		var capturedBody string
		targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			b, _ := io.ReadAll(r.Body)
			capturedBody = string(b)
			w.WriteHeader(http.StatusOK)
		})

		handler := Middleware(targetHandler, "dev")

		reqBody := `{"symbol":"AAPL"}`
		req := httptest.NewRequest(http.MethodPost, "/test?debug=1", strings.NewReader(reqBody))
		req.Header.Set("Authorization", "Bearer super-secret-auth-token")
		req.Header.Set("X-Service-Token", "super-secret-service-token")
		req.Header.Set("Cookie", "session=super-secret-cookie")
		req.Header.Set("Set-Cookie", "tracker=super-secret-tracker")
		req.Header.Set("Accept", "application/json")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if capturedBody != reqBody {
			t.Fatalf("handler did not receive original body: %q", capturedBody)
		}

		out := buf.String()
		if !strings.Contains(out, "incoming http request") {
			t.Fatalf("expected dev mode to log 'incoming http request', got:\n%s", out)
		}
		if !strings.Contains(out, "debug=1") {
			t.Errorf("expected log to contain query debug=1, got:\n%s", out)
		}
		if !strings.Contains(out, "body=") || !strings.Contains(out, "AAPL") {
			t.Errorf("expected log to contain request body, got:\n%s", out)
		}

		// Ensure sensitive tokens are redacted
		if strings.Contains(out, "super-secret-auth-token") {
			t.Errorf("log leaked Authorization header value")
		}
		if strings.Contains(out, "super-secret-service-token") {
			t.Errorf("log leaked X-Service-Token header value")
		}
		if strings.Contains(out, "super-secret-cookie") {
			t.Errorf("log leaked Cookie header value")
		}
		if strings.Contains(out, "super-secret-tracker") {
			t.Errorf("log leaked Set-Cookie header value")
		}
		if !strings.Contains(out, "[REDACTED]") {
			t.Errorf("expected '[REDACTED]' in log output, got:\n%s", out)
		}
	})

	t.Run("prod suppresses debug request details", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := New(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
		})

		handler := Middleware(targetHandler, "prod")

		req := httptest.NewRequest(http.MethodPost, "/test?debug=1", strings.NewReader(`{"symbol":"AAPL"}`))
		req.Header.Set("Authorization", "Bearer secret")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		out := buf.String()
		if strings.Contains(out, "incoming http request") {
			t.Fatalf("prod mode should not emit 'incoming http request', got:\n%s", out)
		}
		if strings.Contains(out, "DEBUG") {
			t.Fatalf("prod mode should not emit DEBUG logs, got:\n%s", out)
		}
		if strings.Contains(out, "AAPL") {
			t.Fatalf("prod mode should not dump request body, got:\n%s", out)
		}
	})
}

func TestLoggingMiddleware_ProviderNameCompliance(t *testing.T) {
	var buf bytes.Buffer
	logger, err := New(&buf, "dev", "DEBUG")
	if err != nil {
		t.Fatalf("newLogger error: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := Middleware(targetHandler, "dev")
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	assertNoProviderName(t, "middleware log", buf.String())
}

// setSlogDefault sets slog's default logger and returns a restore function.
func setSlogDefault(logger *slog.Logger) *slog.Logger {
	prev := slog.Default()
	slog.SetDefault(logger)
	return prev
}

var providerNames = []string{
	"FM" + "P",
	"Poly" + "gon",
	"EOD" + "HD",
}

func assertNoProviderName(t *testing.T, label, text string) {
	t.Helper()
	for _, provider := range providerNames {
		if strings.Contains(strings.ToLower(text), strings.ToLower(provider)) {
			t.Errorf("%s leaked provider %q: %q", label, provider, text)
		}
	}
}

func TestLoggingMiddleware_OTelTraceparentPropagation(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	tp := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	prevTP := otel.GetTracerProvider()
	prevProp := otel.GetTextMapPropagator()
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	t.Cleanup(func() {
		otel.SetTracerProvider(prevTP)
		otel.SetTextMapPropagator(prevProp)
		_ = tp.Shutdown(context.Background())
	})

	const (
		inboundTraceID = "4bf92f3577b34da6a3ce929d0e0e4736"
		inboundSpanID  = "00f067aa0ba902b7"
	)
	inboundTraceparent := "00-" + inboundTraceID + "-" + inboundSpanID + "-01"

	var observedTraceID string
	var innerFlusherCalled bool

	innerHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		span := trace.SpanFromContext(r.Context())
		if span.SpanContext().IsValid() {
			observedTraceID = span.SpanContext().TraceID().String()
		}
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
			innerFlusherCalled = true
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	// Wrap router with otelhttp.NewHandler inside logging.Middleware
	handler := Middleware(otelhttp.NewHandler(innerHandler, "mcp-gateway.http"), "prod")

	req := httptest.NewRequest(http.MethodGet, "/mcp", nil)
	req.Header.Set("Traceparent", inboundTraceparent)
	req.Header.Set("X-Service-Token", "super-secret-token-not-to-leak")
	req.Header.Set("Authorization", "Bearer sensitive-auth-token")
	rec := &flusherRecorder{ResponseRecorder: httptest.NewRecorder()}

	handler.ServeHTTP(rec, req)

	// 1. Verify inbound traceparent is continued
	if observedTraceID != inboundTraceID {
		t.Errorf("observed trace ID = %q, want %q", observedTraceID, inboundTraceID)
	}

	// 2. Verify http.Flusher is preserved through loggingResponseWriter and otelhttp
	if !innerFlusherCalled {
		t.Error("expected inner handler to successfully call Flush via http.Flusher")
	}
	if !rec.flushed {
		t.Error("expected underlying flusherRecorder to have received Flush call")
	}

	// 3. Verify span attributes and trace continuation
	spans := recorder.Ended()
	if len(spans) != 1 {
		t.Fatalf("expected 1 recorded span, got %d", len(spans))
	}
	s := spans[0]
	if s.SpanKind() != trace.SpanKindServer {
		t.Errorf("span kind = %v, want %v", s.SpanKind(), trace.SpanKindServer)
	}
	if s.SpanContext().TraceID().String() != inboundTraceID {
		t.Errorf("recorded span trace ID = %q, want %q", s.SpanContext().TraceID().String(), inboundTraceID)
	}
	if s.Parent().SpanID().String() != inboundSpanID {
		t.Errorf("recorded span parent ID = %q, want %q", s.Parent().SpanID().String(), inboundSpanID)
	}

	// 4. Verify sensitive headers are not leaked into span attributes
	for _, attr := range s.Attributes() {
		key := strings.ToLower(string(attr.Key))
		val := strings.ToLower(attr.Value.AsString())
		if strings.Contains(key, "service-token") || strings.Contains(val, "super-secret-token") {
			t.Errorf("span leaked service-token in attribute %s: %s", attr.Key, attr.Value.AsString())
		}
		if strings.Contains(val, "sensitive-auth-token") {
			t.Errorf("span leaked authorization in attribute %s: %s", attr.Key, attr.Value.AsString())
		}
	}
}

func TestSanitizeHeaders(t *testing.T) {
	headers := http.Header{
		"Authorization":   []string{"Bearer secret-jwt"},
		"X-Service-Token": []string{"secret-token-123"},
		"Cookie":          []string{"session=xyz"},
		"Set-Cookie":      []string{"id=abc; Secure"},
		"X-Request-Id":    []string{"req-1"},
		"Content-Type":    []string{"application/json"},
	}

	sanitized := SanitizeHeaders(headers)

	if val := sanitized["Authorization"]; len(val) != 1 || val[0] != "[REDACTED]" {
		t.Errorf("Authorization = %v, want [[REDACTED]]", val)
	}
	if val := sanitized["X-Service-Token"]; len(val) != 1 || val[0] != "[REDACTED]" {
		t.Errorf("X-Service-Token = %v, want [[REDACTED]]", val)
	}
	if val := sanitized["Cookie"]; len(val) != 1 || val[0] != "[REDACTED]" {
		t.Errorf("Cookie = %v, want [[REDACTED]]", val)
	}
	if val := sanitized["Set-Cookie"]; len(val) != 1 || val[0] != "[REDACTED]" {
		t.Errorf("Set-Cookie = %v, want [[REDACTED]]", val)
	}
	if val := sanitized["X-Request-Id"]; len(val) != 1 || val[0] != "req-1" {
		t.Errorf("X-Request-Id = %v, want [req-1]", val)
	}
	if val := sanitized["Content-Type"]; len(val) != 1 || val[0] != "application/json" {
		t.Errorf("Content-Type = %v, want [application/json]", val)
	}
}
