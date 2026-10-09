package tools

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestGetPriceHistory_OptionalDatesAndInterval(t *testing.T) {
	var capturedQuery url.Values
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedQuery = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"symbol":"AAPL","currency":"USD","from_date":"2023-01-01","to_date":"2024-01-01","interval":"day","items":[]}`))
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	t.Run("without from and to sends neither parameter", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol": "AAPL",
		})
		if res.IsError {
			t.Fatalf("unexpected tool error: %v", resultText(t, res))
		}
		if capturedQuery == nil {
			t.Fatal("backend was not called")
		}
		if capturedQuery.Has("from") {
			t.Errorf("expected no 'from' param, got %q", capturedQuery.Get("from"))
		}
		if capturedQuery.Has("to") {
			t.Errorf("expected no 'to' param, got %q", capturedQuery.Get("to"))
		}
		if capturedQuery.Has("interval") {
			t.Errorf("expected no 'interval' param when empty, got %q", capturedQuery.Get("interval"))
		}
	})

	t.Run("with interval sends interval parameter", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol":   "AAPL",
			"interval": "week",
		})
		if res.IsError {
			t.Fatalf("unexpected tool error: %v", resultText(t, res))
		}
		if capturedQuery.Get("interval") != "week" {
			t.Errorf("expected interval=week, got %q", capturedQuery.Get("interval"))
		}
		if capturedQuery.Has("from") || capturedQuery.Has("to") {
			t.Errorf("expected neither from nor to, got from=%q to=%q", capturedQuery.Get("from"), capturedQuery.Get("to"))
		}
	})

	t.Run("interval validated client-side", func(t *testing.T) {
		capturedQuery = nil
		res := callTool(t, session, "get_price_history", map[string]any{
			"symbol":   "AAPL",
			"interval": "biweekly",
		})
		if !res.IsError {
			t.Fatal("expected error on invalid interval")
		}
		if capturedQuery != nil {
			t.Fatal("backend should not have been called for invalid interval")
		}
		if !strings.Contains(resultText(t, res), "interval must be 'day', 'week', or 'month'") {
			t.Errorf("expected interval error message, got %q", resultText(t, res))
		}
	})
}

func TestGetPriceHistory_Backend422CapErrorForwardedToAgent(t *testing.T) {
	const capErrorMessage = "Requested range spans ~2609 bars, exceeding the limit of 2000. Narrow the date range or use a coarser interval ('week' or 'month')."
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"detail": capErrorMessage,
		})
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	res := callTool(t, session, "get_price_history", map[string]any{
		"symbol": "AAPL",
		"from":   "2015-01-01",
		"to":     "2024-12-31",
	})
	if !res.IsError {
		t.Fatal("expected tool error on backend 422")
	}
	text := resultText(t, res)
	if !strings.Contains(text, capErrorMessage) {
		t.Errorf("expected backend 422 message %q forwarded to agent, got %q", capErrorMessage, text)
	}
}

func TestGetTechnicalIndicator_ClientSideValidationAndPassThrough(t *testing.T) {
	var capturedQuery url.Values
	var capturedPath string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		capturedQuery = r.URL.Query()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"symbol":"AAPL","indicator":"bollinger","currency":"USD","from_date":"2026-01-01","to_date":"2026-01-31","params":{"period":20,"std_dev":2},"points":[{"time":"2026-01-02","value":100.0}]}`))
	}))
	t.Cleanup(backend.Close)

	session := newTestSession(t, backend.URL)

	t.Run("client-side validation rejects invalid indicator before backend", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "unknown",
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for invalid indicator")
		}
		if !strings.Contains(resultText(t, res), "indicator must be 'sma', 'ema', 'rsi', 'macd', or 'bollinger'") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range period", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "rsi",
			"period":    1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for period < 2")
		}
		if !strings.Contains(resultText(t, res), "period must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range fast", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"fast":      1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for fast < 2")
		}
		if !strings.Contains(resultText(t, res), "fast must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range slow", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"slow":      401,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for slow > 400")
		}
		if !strings.Contains(resultText(t, res), "slow must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects out-of-range signal", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "macd",
			"signal":    1,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for signal < 2")
		}
		if !strings.Contains(resultText(t, res), "signal must be between 2 and 400") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("client-side validation rejects non-positive std_dev", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "AAPL",
			"indicator": "bollinger",
			"std_dev":   0,
		})
		if !res.IsError {
			t.Fatal("expected client-side validation error for std_dev <= 0")
		}
		if !strings.Contains(resultText(t, res), "std_dev must be greater than 0") {
			t.Errorf("expected validation message, got: %s", resultText(t, res))
		}
	})

	t.Run("sends query and passes json through", func(t *testing.T) {
		res := callTool(t, session, "get_technical_indicator", map[string]any{
			"symbol":    "aapl",
			"indicator": "bollinger",
			"period":    20,
			"std_dev":   2.0,
			"from":      "2026-01-01",
			"to":        "2026-01-31",
			"exchange":  "nasdaq",
		})
		if res.IsError {
			t.Fatalf("unexpected error: %s", resultText(t, res))
		}
		if capturedPath != "/api/v1/market/data/indicators/AAPL" {
			t.Errorf("captured path = %q, want /api/v1/market/data/indicators/AAPL", capturedPath)
		}
		if capturedQuery.Get("indicator") != "bollinger" {
			t.Errorf("indicator = %q, want bollinger", capturedQuery.Get("indicator"))
		}
		if capturedQuery.Get("period") != "20" {
			t.Errorf("period = %q, want 20", capturedQuery.Get("period"))
		}
		if capturedQuery.Get("std_dev") != "2" {
			t.Errorf("std_dev = %q, want 2", capturedQuery.Get("std_dev"))
		}
		if capturedQuery.Get("exchange") != "NASDAQ" {
			t.Errorf("exchange = %q, want NASDAQ", capturedQuery.Get("exchange"))
		}
		raw := resultText(t, res)
		if !strings.Contains(raw, `"points"`) || !strings.Contains(raw, `"currency":"USD"`) {
			t.Errorf("expected passthrough JSON, got: %s", raw)
		}
	})
}
