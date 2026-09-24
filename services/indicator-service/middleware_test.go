package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
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
	if got := RequestIDFromContext(nil); got != "" {
		t.Errorf("expected empty string for nil context, got %q", got)
	}
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
	customLogger := SetupLogger("prod", "", buf)
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
	logger := SetupLogger("prod", "", buf)
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
	logger := SetupLogger("prod", "", buf)
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
			logger := SetupLogger("prod", "", buf)
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
	logger := SetupLogger("dev", "", buf)
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
	logger := SetupLogger("prod", "", buf)
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
	logger := SetupLogger("prod", "", buf)
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
	logger := SetupLogger("prod", "", buf)

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
