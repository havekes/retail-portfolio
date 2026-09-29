package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"

	"go.opentelemetry.io/otel"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"go.opentelemetry.io/otel/trace"

	"retail-portfolio/services/indicator-service/internal/observability"
)

var uuidV4Regex = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

func TestGenerateRequestID(t *testing.T) {
	seen := make(map[string]struct{})
	for i := 0; i < 100; i++ {
		id := generateRequestID()
		if len(id) != 36 {
			t.Fatalf("expected 36 chars, got %d for %q", len(id), id)
		}
		if !uuidV4Regex.MatchString(id) {
			t.Fatalf("id %q is not a valid UUIDv4", id)
		}
		if _, exists := seen[id]; exists {
			t.Fatalf("duplicate UUID generated: %s", id)
		}
		seen[id] = struct{}{}
	}
}

func TestContextHelpers(t *testing.T) {
	//lint:ignore SA1012 testing nil context resilience
	if got := RequestIDFromContext(nil); got != "" {
		t.Errorf("expected empty string for nil context, got %q", got)
	}
	//lint:ignore SA1012 testing nil context resilience
	if got := LoggerFromContext(nil); got == nil {
		t.Error("expected non-nil logger for nil context")
	}

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	if got := RequestIDFromContext(req.Context()); got != "" {
		t.Errorf("expected empty string for uninstrumented context, got %q", got)
	}

	ctx := WithRequestID(req.Context(), "test-req-id")
	if got := RequestIDFromContext(ctx); got != "test-req-id" {
		t.Errorf("expected test-req-id, got %q", got)
	}

	buf := &bytes.Buffer{}
	customLogger := mustSetupLogger(t, "prod", "", buf)
	ctx = WithLogger(ctx, customLogger)
	if got := LoggerFromContext(ctx); got != customLogger {
		t.Errorf("expected customLogger from context, got %v", got)
	}
}

func TestStatusResponseWriter(t *testing.T) {
	rec := httptest.NewRecorder()
	srw := newStatusResponseWriter(rec)

	if srw.statusCode != http.StatusOK {
		t.Errorf("expected initial status 200, got %d", srw.statusCode)
	}
	if srw.Unwrap() != rec {
		t.Errorf("expected Unwrap to return underlying recorder")
	}

	srw.WriteHeader(http.StatusTeapot)
	if srw.statusCode != http.StatusTeapot {
		t.Errorf("expected status 418, got %d", srw.statusCode)
	}
	// Second WriteHeader call should not change recorded statusCode
	srw.WriteHeader(http.StatusOK)
	if srw.statusCode != http.StatusTeapot {
		t.Errorf("expected status to remain 418, got %d", srw.statusCode)
	}

	n, err := srw.Write([]byte("hello"))
	if err != nil || n != 5 {
		t.Errorf("unexpected write result: %d, %v", n, err)
	}
}

func TestLoggingMiddleware_RequestIDPropagation(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "prod", "", buf)
	router := NewRouter(logger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("X-Request-ID", "existing-id-123")
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	respHeaderID := rec.Header().Get("X-Request-ID")
	if respHeaderID != "existing-id-123" {
		t.Fatalf("expected X-Request-ID header 'existing-id-123', got %q", respHeaderID)
	}

	logOutput := buf.String()
	if !strings.Contains(logOutput, `"request_id":"existing-id-123"`) {
		t.Errorf("expected log to contain request_id existing-id-123, got: %s", logOutput)
	}
}

func TestLoggingMiddleware_RequestIDGeneration(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "prod", "", buf)
	router := NewRouter(logger)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	respHeaderID := rec.Header().Get("X-Request-ID")
	if len(respHeaderID) != 36 {
		t.Fatalf("expected 36-character UUIDv4, got %q (len %d)", respHeaderID, len(respHeaderID))
	}
	if !uuidV4Regex.MatchString(respHeaderID) {
		t.Fatalf("generated ID %q does not match UUIDv4 pattern", respHeaderID)
	}

	logOutput := buf.String()
	if !strings.Contains(logOutput, respHeaderID) {
		t.Errorf("expected log to contain generated request_id %q, got: %s", respHeaderID, logOutput)
	}
}

func TestLoggingMiddleware_StatusCodeAndDuration(t *testing.T) {
	testCases := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{name: "StatusOK_200", method: http.MethodGet, path: "/health", expectedStatus: http.StatusOK},
		{name: "StatusNotFound_404", method: http.MethodGet, path: "/nonexistent-route", expectedStatus: http.StatusNotFound},
		{name: "StatusMethodNotAllowed_405", method: http.MethodPost, path: "/health", expectedStatus: http.StatusMethodNotAllowed},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			buf := &bytes.Buffer{}
			logger := mustSetupLogger(t, "prod", "", buf)
			router := NewRouter(logger)

			req := httptest.NewRequest(tc.method, tc.path, nil)
			rec := httptest.NewRecorder()

			router.ServeHTTP(rec, req)

			if rec.Code != tc.expectedStatus {
				t.Fatalf("expected HTTP status %d, got %d", tc.expectedStatus, rec.Code)
			}

			// In prod mode, find the "http request" log line
			lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
			var requestLog map[string]any
			for _, line := range lines {
				var parsed map[string]any
				if err := json.Unmarshal([]byte(line), &parsed); err == nil {
					if parsed["msg"] == "http request" {
						requestLog = parsed
						break
					}
				}
			}

			if requestLog == nil {
				t.Fatalf("could not find 'http request' log record in:\n%s", buf.String())
			}

			statusVal, ok := requestLog["status"].(float64)
			if !ok || int(statusVal) != tc.expectedStatus {
				t.Errorf("expected log status %d, got %v", tc.expectedStatus, requestLog["status"])
			}

			if _, ok := requestLog["duration_ms"]; !ok {
				t.Errorf("expected log to contain duration_ms, got: %+v", requestLog)
			}
		})
	}
}

func TestLoggingMiddleware_DevPayloadLogging(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "dev", "", buf)
	router := NewRouter(logger)

	payload := map[string]any{
		"interval": "1d",
		"candles": []map[string]any{
			{"time": "2024-01-01", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
			{"time": "2024-01-02", "open": 11, "high": 13, "low": 10, "close": 12, "volume": 110},
		},
		"indicators": []map[string]any{
			{"type": "sma", "period": 2},
		},
	}
	payloadBytes, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(payloadBytes))
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d: %s", rec.Code, rec.Body.String())
	}

	// Verify indicators were computed despite body being read by middleware
	var resp struct {
		Indicators map[string]any `json:"indicators"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode compute response: %v", err)
	}
	if len(resp.Indicators) == 0 {
		t.Fatalf("expected computed indicators in response, got empty")
	}

	logOutput := buf.String()
	if !strings.Contains(logOutput, "DEBUG") {
		t.Errorf("expected DEBUG log record in dev mode, got:\n%s", logOutput)
	}
	if !strings.Contains(logOutput, "body=") || !strings.Contains(logOutput, "candles") || !strings.Contains(logOutput, "sma") {
		t.Errorf("expected DEBUG log to contain body payload, got:\n%s", logOutput)
	}
}

func TestLoggingMiddleware_ProdNormalRequest_NoBodyDump(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "prod", "", buf)
	router := NewRouter(logger)

	payload := map[string]any{
		"interval": "1d",
		"candles": []map[string]any{
			{"time": "2024-01-01", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100},
			{"time": "2024-01-02", "open": 11, "high": 13, "low": 10, "close": 12, "volume": 110},
		},
		"indicators": []map[string]any{
			{"type": "sma", "period": 2},
		},
	}
	payloadBytes, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(payloadBytes))
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d: %s", rec.Code, rec.Body.String())
	}

	logOutput := buf.String()
	var parsed map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(logOutput)), &parsed); err != nil {
		t.Fatalf("failed to parse json log: %v\nOutput: %s", err, logOutput)
	}

	if parsed["level"] != "INFO" {
		t.Errorf("expected level INFO, got %v", parsed["level"])
	}
	if parsed["status"] != float64(200) {
		t.Errorf("expected status 200, got %v", parsed["status"])
	}
	if _, ok := parsed["duration_ms"]; !ok {
		t.Errorf("expected duration_ms attribute, got %+v", parsed)
	}
	if _, ok := parsed["request_id"]; !ok {
		t.Errorf("expected request_id attribute, got %+v", parsed)
	}
	if _, hasBody := parsed["body"]; hasBody {
		t.Errorf("expected no body dump in prod mode, but body was present: %v", parsed["body"])
	}
}

func TestLoggingMiddleware_ErrorStatusCodes(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "prod", "", buf)
	router := NewRouter(logger)

	// Send malformed JSON to trigger 400
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBufferString("{invalid-json}"))
	rec := httptest.NewRecorder()

	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 Bad Request, got %d", rec.Code)
	}

	lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
	var requestLog map[string]any
	for _, line := range lines {
		var parsed map[string]any
		if err := json.Unmarshal([]byte(line), &parsed); err == nil {
			if parsed["msg"] == "http request" {
				requestLog = parsed
				break
			}
		}
	}

	if requestLog == nil {
		t.Fatalf("could not find 'http request' log record in:\n%s", buf.String())
	}

	if requestLog["level"] != "WARN" {
		t.Errorf("expected WARN level for 400 status, got %v", requestLog["level"])
	}
	if requestLog["path"] != "/compute" {
		t.Errorf("expected path /compute, got %v", requestLog["path"])
	}
	if requestLog["status"] != float64(400) {
		t.Errorf("expected status 400, got %v", requestLog["status"])
	}
	if _, ok := requestLog["request_id"]; !ok {
		t.Errorf("expected request_id in log, got %+v", requestLog)
	}
}

func TestLoggingMiddleware_ServerErrorStatus(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := mustSetupLogger(t, "prod", "", buf)

	// Middleware wrapping a handler that returns 500
	handler := LoggingMiddleware(logger)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))

	req := httptest.NewRequest(http.MethodGet, "/fail", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500 status, got %d", rec.Code)
	}

	var parsed map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(buf.String())), &parsed); err != nil {
		t.Fatalf("failed to parse log: %v", err)
	}

	if parsed["level"] != "ERROR" {
		t.Errorf("expected ERROR level for 500 status, got %v", parsed["level"])
	}
	if parsed["status"] != float64(500) {
		t.Errorf("expected status 500, got %v", parsed["status"])
	}
}

func TestLoggingMiddleware_NilLoggerFallback(t *testing.T) {
	middleware := LoggingMiddleware(nil)
	handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if rec.Header().Get("X-Request-ID") == "" {
		t.Error("expected generated X-Request-ID header")
	}
}

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

func testProvider(t *testing.T) *tracetest.SpanRecorder {
	t.Helper()

	otel.SetTextMapPropagator(observability.NewPropagator())

	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	restore := observability.SetTracerProvider(provider)
	t.Cleanup(func() {
		restore()
		_ = provider.Shutdown(context.Background())
	})
	return recorder
}

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

func servedHandler() http.Handler {
	return NewRouter(slog.Default())
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
