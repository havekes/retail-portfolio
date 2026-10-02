package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func parseLogRecords(output string) []map[string]any {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	var records []map[string]any
	for _, line := range lines {
		var rec map[string]any
		if err := json.Unmarshal([]byte(line), &rec); err == nil {
			records = append(records, rec)
		}
	}
	return records
}

func findLogRecord(records []map[string]any, msg string) map[string]any {
	for _, rec := range records {
		if rec["msg"] == msg {
			return rec
		}
	}
	return nil
}

func TestHealthHandler(t *testing.T) {
	router := NewRouter()

	// GET /health -> 200
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	var health HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &health); err != nil {
		t.Fatalf("failed to unmarshal health response: %v", err)
	}
	if health.Status != "ok" || health.Service != "indicator-service" {
		t.Errorf("unexpected health response: %+v", health)
	}

	// POST /health -> 405
	reqPost := httptest.NewRequest(http.MethodPost, "/health", nil)
	recPost := httptest.NewRecorder()
	router.ServeHTTP(recPost, reqPost)
	if recPost.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", recPost.Code)
	}
}

func TestHealthHandler_MethodNotAllowed_Logging(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := SetupLogger("prod", "", buf)
	router := NewRouter(logger)

	req := httptest.NewRequest(http.MethodPost, "/health", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected status 405, got %d", rec.Code)
	}

	records := parseLogRecords(buf.String())
	warnRecord := findLogRecord(records, "method not allowed")
	if warnRecord == nil {
		t.Fatalf("expected warn log with msg 'method not allowed', got:\n%s", buf.String())
	}
	if warnRecord["level"] != "WARN" {
		t.Errorf("expected WARN level, got %v", warnRecord["level"])
	}
	if warnRecord["path"] != "/health" {
		t.Errorf("expected path /health, got %v", warnRecord["path"])
	}
	if _, ok := warnRecord["request_id"]; !ok {
		t.Errorf("expected request_id in warn log, got %+v", warnRecord)
	}
	if errStr, ok := warnRecord["error"].(string); !ok || errStr != "method not allowed" {
		t.Errorf("expected error field 'method not allowed', got %+v", warnRecord)
	}
}

func TestComputeHandler_MethodNotAllowed(t *testing.T) {
	router := NewRouter()
	req := httptest.NewRequest(http.MethodGet, "/compute", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", rec.Code)
	}
}

func TestComputeHandler_MethodNotAllowed_Logging(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := SetupLogger("prod", "", buf)
	router := NewRouter(logger)

	req := httptest.NewRequest(http.MethodGet, "/compute", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected status 405, got %d", rec.Code)
	}

	records := parseLogRecords(buf.String())
	warnRecord := findLogRecord(records, "method not allowed")
	if warnRecord == nil {
		t.Fatalf("expected warn log with msg 'method not allowed', got:\n%s", buf.String())
	}
	if warnRecord["level"] != "WARN" {
		t.Errorf("expected WARN level, got %v", warnRecord["level"])
	}
	if warnRecord["path"] != "/compute" {
		t.Errorf("expected path /compute, got %v", warnRecord["path"])
	}
	if _, ok := warnRecord["request_id"]; !ok {
		t.Errorf("expected request_id in warn log, got %+v", warnRecord)
	}
	if errStr, ok := warnRecord["error"].(string); !ok || errStr != "method not allowed" {
		t.Errorf("expected error field 'method not allowed', got %+v", warnRecord)
	}
}

func TestComputeHandler_InvalidJSON(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := SetupLogger("prod", "", buf)
	router := NewRouter(logger)

	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBufferString("{invalid-json}"))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", rec.Code)
	}

	records := parseLogRecords(buf.String())
	errRecord := findLogRecord(records, "malformed json payload")
	if errRecord == nil {
		t.Fatalf("expected error log with msg 'malformed json payload', got:\n%s", buf.String())
	}
	if errRecord["level"] != "ERROR" {
		t.Errorf("expected ERROR level, got %v", errRecord["level"])
	}
	if errRecord["path"] != "/compute" {
		t.Errorf("expected path /compute, got %v", errRecord["path"])
	}
	if _, ok := errRecord["request_id"]; !ok {
		t.Errorf("expected request_id in error log, got %+v", errRecord)
	}
	if errStr, ok := errRecord["error"].(string); !ok || errStr == "" {
		t.Errorf("expected non-empty error field in error log, got %+v", errRecord)
	}
}

func TestComputeHandler_UnknownIndicator(t *testing.T) {
	buf := &bytes.Buffer{}
	logger := SetupLogger("prod", "", buf)
	router := NewRouter(logger)

	payload := ComputeRequest{
		Interval: "1d",
		Candles: []Candle{
			{Time: "2024-01-01", Open: 10, High: 12, Low: 9, Close: 11, Volume: 100},
		},
		Indicators: []IndicatorSpec{
			{Type: "non_existent_indicator"},
		},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status 400 for unknown indicator, got %d", rec.Code)
	}

	records := parseLogRecords(buf.String())
	errRecord := findLogRecord(records, "indicator calculation failed")
	if errRecord == nil {
		t.Fatalf("expected error log with msg 'indicator calculation failed', got:\n%s", buf.String())
	}
	if errRecord["level"] != "ERROR" {
		t.Errorf("expected ERROR level, got %v", errRecord["level"])
	}
	if errRecord["path"] != "/compute" {
		t.Errorf("expected path /compute, got %v", errRecord["path"])
	}
	if _, ok := errRecord["request_id"]; !ok {
		t.Errorf("expected request_id in error log, got %+v", errRecord)
	}
	if errStr, ok := errRecord["error"].(string); !ok || errStr == "" {
		t.Errorf("expected non-empty error field in error log, got %+v", errRecord)
	}
}

func TestComputeHandler_PreserveTimestamps_DailyString(t *testing.T) {
	router := NewRouter()
	payload := map[string]any{
		"interval": "1d",
		"candles": []map[string]any{
			{"time": "2024-01-01", "open": 10, "high": 12, "low": 9, "close": 10, "volume": 100},
			{"time": "2024-01-02", "open": 20, "high": 22, "low": 19, "close": 20, "volume": 200},
			{"time": "2024-01-03", "open": 30, "high": 32, "low": 29, "close": 30, "volume": 300},
		},
		"indicators": []map[string]any{
			{"type": "sma", "period": 2},
		},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var resp struct {
		Indicators map[string][]struct {
			Time  string  `json:"time"`
			Value float64 `json:"value"`
		} `json:"indicators"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	smaPoints := resp.Indicators["sma"]
	if len(smaPoints) != 2 {
		t.Fatalf("expected 2 SMA points, got %d", len(smaPoints))
	}
	if smaPoints[0].Time != "2024-01-02" {
		t.Errorf("expected time 2024-01-02, got %q", smaPoints[0].Time)
	}
	if smaPoints[1].Time != "2024-01-03" {
		t.Errorf("expected time 2024-01-03, got %q", smaPoints[1].Time)
	}
}

func TestComputeHandler_PreserveTimestamps_IntradayNumber(t *testing.T) {
	router := NewRouter()
	payload := map[string]any{
		"interval": "1h",
		"candles": []map[string]any{
			{"time": 1704067200, "open": 10, "high": 12, "low": 9, "close": 10, "volume": 100},
			{"time": 1704070800, "open": 20, "high": 22, "low": 19, "close": 20, "volume": 200},
			{"time": 1704074400, "open": 30, "high": 32, "low": 29, "close": 30, "volume": 300},
		},
		"indicators": []map[string]any{
			{"type": "sma", "period": 2},
		},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var resp struct {
		Indicators map[string][]struct {
			Time  int64   `json:"time"`
			Value float64 `json:"value"`
		} `json:"indicators"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	smaPoints := resp.Indicators["sma"]
	if len(smaPoints) != 2 {
		t.Fatalf("expected 2 SMA points, got %d", len(smaPoints))
	}
	if smaPoints[0].Time != 1704070800 {
		t.Errorf("expected time 1704070800, got %d", smaPoints[0].Time)
	}
	if smaPoints[1].Time != 1704074400 {
		t.Errorf("expected time 1704074400, got %d", smaPoints[1].Time)
	}
}

func TestComputeHandler_FullSuiteAndCustomID(t *testing.T) {
	router := NewRouter()

	// Generate 60 candles
	candles := make([]Candle, 60)
	for i := range candles {
		c := float64(100 + i)
		candles[i] = Candle{
			Time:   1704067200 + i*86400,
			Open:   c,
			High:   c + 2,
			Low:    c - 2,
			Close:  c,
			Volume: float64(1000 + i*10),
		}
	}

	payload := ComputeRequest{
		Interval: "1d",
		Candles:  candles,
		Indicators: []IndicatorSpec{
			{ID: "my_custom_ma50", Type: "ma50"},
			{Type: "ma200"},
			{Type: "ma50w"},
			{Type: "ma200w"},
			{Type: "bb"},
			{Type: "macd"},
			{Type: "rsi"},
			{Type: "obv"},
		},
	}

	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var rawResp map[string]map[string]json.RawMessage
	if err := json.Unmarshal(rec.Body.Bytes(), &rawResp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	indicators := rawResp["indicators"]
	expectedKeys := []string{
		"my_custom_ma50",
		"ma200",
		"ma50w",
		"ma200w",
		"bb",
		"macd",
		"rsi",
		"obv",
	}

	for _, key := range expectedKeys {
		if _, ok := indicators[key]; !ok {
			t.Errorf("expected key %q in response indicators", key)
		}
	}
}

func TestComputeHandler_EmptyCandles(t *testing.T) {
	router := NewRouter()
	payload := ComputeRequest{
		Interval: "1d",
		Candles:  []Candle{},
		Indicators: []IndicatorSpec{
			{Type: "ma50"},
			{Type: "bb"},
			{Type: "macd"},
			{Type: "rsi"},
			{Type: "obv"},
		},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBuffer(body))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var resp struct {
		Indicators map[string][]any `json:"indicators"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	for k, v := range resp.Indicators {
		if len(v) != 0 {
			t.Errorf("expected empty array for %s, got len %d", k, len(v))
		}
	}
}
