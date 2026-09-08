package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

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

func TestComputeHandler_MethodNotAllowed(t *testing.T) {
	router := NewRouter()
	req := httptest.NewRequest(http.MethodGet, "/compute", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("expected status 405, got %d", rec.Code)
	}
}

func TestComputeHandler_InvalidJSON(t *testing.T) {
	router := NewRouter()
	req := httptest.NewRequest(http.MethodPost, "/compute", bytes.NewBufferString("{invalid-json}"))
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("expected status 400, got %d", rec.Code)
	}
}

func TestComputeHandler_UnknownIndicator(t *testing.T) {
	router := NewRouter()
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
