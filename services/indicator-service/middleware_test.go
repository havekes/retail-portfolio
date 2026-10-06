package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

// Compile-time guarantees that wrapping the writer keeps the optional
// interfaces the standard server relies on.
var (
	_ http.Flusher  = (*statusResponseWriter)(nil)
	_ http.Hijacker = (*statusResponseWriter)(nil)
)

const (
	testTraceID      = "4bf92f3577b34da6a3ce929d0e0e4736"
	testParentSpanID = "00f067aa0ba902b7"
	testTraceparent  = "00-" + testTraceID + "-" + testParentSpanID + "-01"
)

// computeRequestBody builds a valid /compute payload with the given number of
// candles and indicators.
func computeRequestBody(t *testing.T, candles, indicators int) []byte {
	t.Helper()

	candleList := make([]map[string]any, 0, candles)
	for i := range candles {
		price := float64(10 + i)
		candleList = append(candleList, map[string]any{
			"time":   fmt.Sprintf("2024-01-%02d", i+1),
			"open":   price,
			"high":   price + 1,
			"low":    price - 1,
			"close":  price,
			"volume": 100,
		})
	}

	indicatorList := make([]map[string]any, 0, indicators)
	for range indicators {
		indicatorList = append(indicatorList, map[string]any{"type": "sma", "period": 2})
	}

	payload, err := json.Marshal(map[string]any{
		"interval":   "1d",
		"candles":    candleList,
		"indicators": indicatorList,
	})
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}
	return payload
}

// servedHandler is the production middleware chain around the real router.
func servedHandler() http.Handler {
	return TraceMiddleware(RequestIDMiddleware(NewRouter()))
}

func serveCompute(t *testing.T, body []byte, headers map[string]string) (*http.Response, *httptest.ResponseRecorder) {
	t.Helper()

	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	rec := httptest.NewRecorder()
	servedHandler().ServeHTTP(rec, req)

	return rec.Result(), rec
}

func spanAttribute(t *testing.T, span sdktrace.ReadOnlySpan, key string) string {
	t.Helper()
	for _, attr := range span.Attributes() {
		if string(attr.Key) == key {
			return attr.Value.Emit()
		}
	}
	t.Fatalf("span %q has no attribute %q", span.Name(), key)
	return ""
}

func spansByName(spans []sdktrace.ReadOnlySpan, name string) []sdktrace.ReadOnlySpan {
	matched := []sdktrace.ReadOnlySpan{}
	for _, span := range spans {
		if span.Name() == name {
			matched = append(matched, span)
		}
	}
	return matched
}

func TestTraceMiddlewareContinuesInboundTraceparent(t *testing.T) {
	recorder := testProvider(t)

	resp, _ := serveCompute(t, computeRequestBody(t, 3, 1), map[string]string{
		"traceparent": testTraceparent,
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected status 200, got %d", resp.StatusCode)
	}

	spans := recorder.Ended()
	if len(spans) != 2 {
		t.Fatalf("expected 2 spans (server + compute), got %d", len(spans))
	}

	var serverSpan, computeSpan sdktrace.ReadOnlySpan
	for _, span := range spans {
		if span.SpanKind() == trace.SpanKindServer {
			serverSpan = span
			continue
		}
		computeSpan = span
	}
	if serverSpan == nil || computeSpan == nil {
		t.Fatalf("expected a server span and a compute span, got %v", spans)
	}

	// The server span continues the inbound traceparent as a remote parent.
	inboundTraceID, err := trace.TraceIDFromHex(testTraceID)
	if err != nil {
		t.Fatalf("invalid test trace id: %v", err)
	}
	inboundSpanID, err := trace.SpanIDFromHex(testParentSpanID)
	if err != nil {
		t.Fatalf("invalid test span id: %v", err)
	}
	if serverSpan.SpanContext().TraceID() != inboundTraceID {
		t.Errorf("server span trace id = %s, want %s", serverSpan.SpanContext().TraceID(), inboundTraceID)
	}
	if parent := serverSpan.Parent(); parent.TraceID() != inboundTraceID || parent.SpanID() != inboundSpanID {
		t.Errorf("server span parent = %v, want %s/%s", parent, inboundTraceID, inboundSpanID)
	}
	if !serverSpan.Parent().IsRemote() {
		t.Error("server span parent is not marked remote")
	}
	if !serverSpan.SpanContext().IsSampled() {
		t.Error("server span did not inherit the sampled flag from the traceparent")
	}
	if serverSpan.Name() != "POST /compute" {
		t.Errorf("server span name = %q, want %q", serverSpan.Name(), "POST /compute")
	}
	if got := spanAttribute(t, serverSpan, "http.method"); got != http.MethodPost {
		t.Errorf("server span http.method = %q, want %q", got, http.MethodPost)
	}
	if got := spanAttribute(t, serverSpan, "http.route"); got != "/compute" {
		t.Errorf("server span http.route = %q, want %q", got, "/compute")
	}
	if got := spanAttribute(t, serverSpan, "http.status_code"); got != "200" {
		t.Errorf("server span http.status_code = %q, want %q", got, "200")
	}

	// The compute span is a child of the server span, in the same trace.
	if computeSpan.SpanContext().TraceID() != inboundTraceID {
		t.Errorf("compute span trace id = %s, want %s", computeSpan.SpanContext().TraceID(), inboundTraceID)
	}
	if parent := computeSpan.Parent(); parent.TraceID() != serverSpan.SpanContext().TraceID() || parent.SpanID() != serverSpan.SpanContext().SpanID() {
		t.Errorf("compute span parent = %v, want %v", parent, serverSpan.SpanContext())
	}
	if computeSpan.SpanKind() != trace.SpanKindInternal {
		t.Errorf("compute span kind = %v, want internal", computeSpan.SpanKind())
	}
	if got := spanAttribute(t, computeSpan, "indicators.count"); got != "1" {
		t.Errorf("compute span indicators.count = %q, want %q", got, "1")
	}
	if got := spanAttribute(t, computeSpan, "candles.count"); got != "3" {
		t.Errorf("compute span candles.count = %q, want %q", got, "3")
	}
	if got := spanAttribute(t, computeSpan, "http.status_code"); got != "200" {
		t.Errorf("compute span http.status_code = %q, want %q", got, "200")
	}
}

func TestTraceMiddlewareStartsRootSpanWithoutTraceparent(t *testing.T) {
	recorder := testProvider(t)

	resp, _ := serveCompute(t, computeRequestBody(t, 3, 1), nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected status 200, got %d", resp.StatusCode)
	}

	spans := spansByName(recorder.Ended(), "POST /compute")
	if len(spans) != 2 {
		t.Fatalf("expected 2 spans, got %d", len(spans))
	}
	for _, span := range spans {
		if span.Parent().IsValid() && span.Parent().IsRemote() {
			t.Errorf("span %v unexpectedly has a remote parent without a traceparent header", span.SpanContext())
		}
		if !span.SpanContext().TraceID().IsValid() {
			t.Error("span has no trace id")
		}
	}
}

func TestComputeSpanCarriesFailureStatus(t *testing.T) {
	recorder := testProvider(t)

	payload := map[string]any{
		"interval": "1d",
		"candles": []map[string]any{
			{"time": "2024-01-01", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
		},
		"indicators": []map[string]any{{"type": "not-a-real-indicator"}},
	}
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}

	resp, _ := serveCompute(t, body, nil)
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", resp.StatusCode)
	}

	spans := recorder.Ended()
	if len(spans) != 2 {
		t.Fatalf("expected 2 spans, got %d", len(spans))
	}
	for _, span := range spans {
		if got := spanAttribute(t, span, "http.status_code"); got != "400" {
			t.Errorf("span %q http.status_code = %q, want %q", span.Name(), got, "400")
		}
	}
}

func TestRequestIDMiddlewareHonoursInboundRequestID(t *testing.T) {
	var observed string
	handler := RequestIDMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		observed = RequestIDFromContext(r.Context())
		w.WriteHeader(http.StatusNoContent)
	}))

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set(requestIDHeader, "upstream-request-id")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if observed != "upstream-request-id" {
		t.Errorf("request id in context = %q, want %q", observed, "upstream-request-id")
	}
	if got := rec.Header().Get(requestIDHeader); got != "upstream-request-id" {
		t.Errorf("response %s = %q, want %q", requestIDHeader, got, "upstream-request-id")
	}
}

func TestRequestIDMiddlewareGeneratesRequestID(t *testing.T) {
	var observed string
	handler := RequestIDMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		observed = RequestIDFromContext(r.Context())
		w.WriteHeader(http.StatusNoContent)
	}))

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if observed == "" {
		t.Error("expected a generated request id in the context")
	}
	if got := rec.Header().Get(requestIDHeader); got != observed {
		t.Errorf("response %s = %q, want %q", requestIDHeader, got, observed)
	}
}

func TestRequestIDFromContextWithoutRequestID(t *testing.T) {
	if got := RequestIDFromContext(context.Background()); got != "" {
		t.Errorf("request id = %q, want empty", got)
	}
}

func TestStatusResponseWriterCapturesStatus(t *testing.T) {
	tests := []struct {
		name  string
		write func(http.ResponseWriter)
		want  int
	}{
		{
			name:  "explicit 200",
			write: func(w http.ResponseWriter) { w.WriteHeader(http.StatusOK) },
			want:  http.StatusOK,
		},
		{
			name:  "implicit 200 on body write",
			write: func(w http.ResponseWriter) { _, _ = w.Write([]byte("ok")) },
			want:  http.StatusOK,
		},
		{
			name:  "400",
			write: func(w http.ResponseWriter) { w.WriteHeader(http.StatusBadRequest) },
			want:  http.StatusBadRequest,
		},
		{
			name:  "405",
			write: func(w http.ResponseWriter) { w.WriteHeader(http.StatusMethodNotAllowed) },
			want:  http.StatusMethodNotAllowed,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			writer := &statusResponseWriter{ResponseWriter: rec}
			tt.write(writer)

			if got := writer.Status(); got != tt.want {
				t.Errorf("Status() = %d, want %d", got, tt.want)
			}
			if rec.Code != tt.want {
				t.Errorf("underlying recorder code = %d, want %d", rec.Code, tt.want)
			}
		})
	}
}
