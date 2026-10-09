package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"retail-portfolio/services/mcp-gateway/internal/backend"
)

func TestRankSymbolMatches(t *testing.T) {
	t.Run("tier 1 exact symbol on preferred exchange beats earlier matches", func(t *testing.T) {
		// Acceptance criterion 2:
		// [SHOPX/NYSE, SHOP/NYSE, SHOP/TSX] and query="shop", exchange="TSX" =>
		// best_match.symbol == "SHOP" with exchange_short_name == "TSX", and
		// alternatives contain the other two in backend order.
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPX","name":"Shopify X","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify CA","exchange_short_name":"TSX"}`),
		}

		best, alts, err := rankSymbolMatches(items, "shop", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" || bestItem["exchange_short_name"] != "TSX" {
			t.Errorf("bestItem = %+v, want SHOP/TSX", bestItem)
		}

		if len(alts) != 2 {
			t.Fatalf("len(alts) = %d, want 2", len(alts))
		}
		var alt0, alt1 map[string]any
		if err := json.Unmarshal(alts[0], &alt0); err != nil {
			t.Fatalf("unmarshal alt0: %v", err)
		}
		if err := json.Unmarshal(alts[1], &alt1); err != nil {
			t.Fatalf("unmarshal alt1: %v", err)
		}
		if alt0["symbol"] != "SHOPX" || alt0["exchange_short_name"] != "NYSE" {
			t.Errorf("alt0 = %+v, want SHOPX/NYSE", alt0)
		}
		if alt1["symbol"] != "SHOP" || alt1["exchange_short_name"] != "NYSE" {
			t.Errorf("alt1 = %+v, want SHOP/NYSE", alt1)
		}
	})

	t.Run("tier 2 exact symbol match anywhere beats earlier partial match without exchange", func(t *testing.T) {
		// Acceptance criterion 3:
		// Without exchange, an exact symbol match beats an earlier partial match.
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPPING","name":"Shopping Inc","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" {
			t.Errorf("bestItem symbol = %v, want SHOP", bestItem["symbol"])
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
		var altItem map[string]any
		if err := json.Unmarshal(alts[0], &altItem); err != nil {
			t.Fatalf("unmarshal alt: %v", err)
		}
		if altItem["symbol"] != "SHOPPING" {
			t.Errorf("altItem symbol = %v, want SHOPPING", altItem["symbol"])
		}
	})

	t.Run("tier 2 exact symbol match anywhere beats tier 3 partial match on preferred exchange", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOPPING","name":"Shopping CA","exchange_short_name":"TSX"}`),
			json.RawMessage(`{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP" || bestItem["exchange_short_name"] != "NYSE" {
			t.Errorf("bestItem = %+v, want SHOP/NYSE", bestItem)
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
	})

	t.Run("tier 3 first result on preferred exchange beats earlier partial match on other exchange", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOP-US","name":"Shop US","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP-CA1","name":"Shop CA 1","exchange_short_name":"TSX"}`),
			json.RawMessage(`{"symbol":"SHOP-CA2","name":"Shop CA 2","exchange_short_name":"TSX"}`),
		}

		best, alts, err := rankSymbolMatches(items, "SHOP", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP-CA1" {
			t.Errorf("bestItem symbol = %v, want SHOP-CA1", bestItem["symbol"])
		}
		if len(alts) != 2 {
			t.Fatalf("len(alts) = %d, want 2", len(alts))
		}
	})

	t.Run("tier 4 first result when preferred exchange matches nothing", func(t *testing.T) {
		// Risk mitigation: if preferred exchange matches nothing, fall back cleanly to tier 4
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"SHOP-A","name":"Shop A","exchange_short_name":"NYSE"}`),
			json.RawMessage(`{"symbol":"SHOP-B","name":"Shop B","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "xyz", "LSE")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SHOP-A" {
			t.Errorf("bestItem symbol = %v, want SHOP-A", bestItem["symbol"])
		}
		if len(alts) != 1 {
			t.Fatalf("len(alts) = %d, want 1", len(alts))
		}
	})

	t.Run("capping alternatives at max 10", func(t *testing.T) {
		// Acceptance criterion 4:
		// With 15 backend results, alternatives has 10 items.
		items := make([]json.RawMessage, 15)
		for i := 0; i < 15; i++ {
			items[i] = json.RawMessage(fmt.Sprintf(`{"symbol":"SYM%d","exchange_short_name":"NYSE"}`, i))
		}

		best, alts, err := rankSymbolMatches(items, "query", "")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		var bestItem map[string]any
		if err := json.Unmarshal(best, &bestItem); err != nil {
			t.Fatalf("unmarshal best: %v", err)
		}
		if bestItem["symbol"] != "SYM0" {
			t.Errorf("bestItem symbol = %v, want SYM0", bestItem["symbol"])
		}
		if len(alts) != 10 {
			t.Fatalf("len(alts) = %d, want 10", len(alts))
		}
	})

	t.Run("single result yields empty alternatives slice", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`{"symbol":"AAPL","exchange_short_name":"NASDAQ"}`),
		}

		best, alts, err := rankSymbolMatches(items, "AAPL", "NASDAQ")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if best == nil {
			t.Fatal("expected non-nil best")
		}
		if len(alts) != 0 {
			t.Fatalf("len(alts) = %d, want 0", len(alts))
		}
		out, err := json.Marshal(resolveSymbolResult{BestMatch: best, Alternatives: alts})
		if err != nil {
			t.Fatalf("marshal resolveSymbolResult: %v", err)
		}
		if !strings.Contains(string(out), `"alternatives":[]`) {
			t.Errorf("expected alternatives:[], got: %s", string(out))
		}
	})

	t.Run("unknown fields pass through unchanged", func(t *testing.T) {
		// Acceptance criterion 6:
		// Unknown fields on result items pass through unchanged.
		rawItem := `{"symbol":"SHOP","exchange_short_name":"TSX","custom_field":"hello","nested":{"key":123}}`
		items := []json.RawMessage{
			json.RawMessage(rawItem),
		}

		best, _, err := rankSymbolMatches(items, "shop", "TSX")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if string(best) != rawItem {
			t.Errorf("best = %s, want %s", string(best), rawItem)
		}
	})

	t.Run("empty items returns ErrNoData", func(t *testing.T) {
		_, _, err := rankSymbolMatches([]json.RawMessage{}, "shop", "TSX")
		if !errors.Is(err, backend.ErrNoData) {
			t.Fatalf("expected ErrNoData, got: %v", err)
		}
	})

	t.Run("malformed json returns ErrProvider", func(t *testing.T) {
		items := []json.RawMessage{
			json.RawMessage(`not-json`),
		}
		_, _, err := rankSymbolMatches(items, "shop", "TSX")
		if !errors.Is(err, backend.ErrProvider) {
			t.Fatalf("expected ErrProvider, got: %v", err)
		}
	})
}

func TestResolveSymbolToolIntegration(t *testing.T) {
	t.Run("unsupported exchange rejected before backend call", func(t *testing.T) {
		// Acceptance criterion 5:
		// An unsupported exchange is rejected before any backend call (T01 validator)
		backendCalls := 0
		backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			backendCalls++
			w.WriteHeader(http.StatusOK)
		}))
		defer backend.Close()

		session := newTestSession(t, backend.URL)
		res := callTool(t, session, "resolve_symbol", map[string]any{
			"query":    "apple",
			"exchange": "INVALID",
		})
		if !res.IsError {
			t.Fatal("expected error result for unsupported exchange")
		}
		if backendCalls != 0 {
			t.Errorf("backend calls = %d, want 0", backendCalls)
		}
		msg := resultText(t, res)
		if !strings.Contains(msg, "exchange must be one of") {
			t.Errorf("error text = %q, want exchange must be one of", msg)
		}
	})

	t.Run("backend 404 yields no-data result", func(t *testing.T) {
		// Acceptance criterion 5:
		// backend 404 still yields the no-data result
		backend, _ := newStubBackend(t, http.StatusNotFound, `{"detail":"No market data found for 'unknown'."}`)
		session := newTestSession(t, backend.URL)

		res := callTool(t, session, "resolve_symbol", map[string]any{"query": "unknown"})
		if res.IsError {
			t.Fatalf("expected successful no-data result, got error: %s", resultText(t, res))
		}
		msg := resultText(t, res)
		if msg != noDataMessage {
			t.Errorf("result text = %q, want %q", msg, noDataMessage)
		}
	})

	t.Run("end to end ranking and unknown fields pass-through", func(t *testing.T) {
		// Acceptance criteria 2 and 6 end-to-end
		fixture := `[
			{"symbol":"SHOPX","name":"Shopify X","exchange_short_name":"NYSE","custom_score":10},
			{"symbol":"SHOP","name":"Shopify US","exchange_short_name":"NYSE","custom_score":20},
			{"symbol":"SHOP","name":"Shopify CA","exchange_short_name":"TSX","custom_score":30}
		]`
		backend, captured := newStubBackend(t, http.StatusOK, fixture)
		session := newTestSession(t, backend.URL)

		res := callTool(t, session, "resolve_symbol", map[string]any{
			"query":    "shop",
			"exchange": "TSX",
		})
		if res.IsError {
			t.Fatalf("callTool failed: %s", resultText(t, res))
		}

		if captured.path != "/api/v1/market/data/symbols/search" {
			t.Errorf("path = %q, want /api/v1/market/data/symbols/search", captured.path)
		}
		if captured.query.Get("q") != "shop" {
			t.Errorf("query q = %q, want shop", captured.query.Get("q"))
		}

		var payload struct {
			BestMatch    map[string]any   `json:"best_match"`
			Alternatives []map[string]any `json:"alternatives"`
		}
		if err := json.Unmarshal([]byte(resultText(t, res)), &payload); err != nil {
			t.Fatalf("unmarshal payload: %v", err)
		}

		if payload.BestMatch["symbol"] != "SHOP" || payload.BestMatch["exchange_short_name"] != "TSX" {
			t.Errorf("best match = %+v, want SHOP/TSX", payload.BestMatch)
		}
		if payload.BestMatch["custom_score"] != float64(30) {
			t.Errorf("custom_score = %v, want 30", payload.BestMatch["custom_score"])
		}

		if len(payload.Alternatives) != 2 {
			t.Fatalf("len(alternatives) = %d, want 2", len(payload.Alternatives))
		}
		if payload.Alternatives[0]["symbol"] != "SHOPX" || payload.Alternatives[0]["custom_score"] != float64(10) {
			t.Errorf("alt 0 = %+v", payload.Alternatives[0])
		}
		if payload.Alternatives[1]["symbol"] != "SHOP" || payload.Alternatives[1]["custom_score"] != float64(20) {
			t.Errorf("alt 1 = %+v", payload.Alternatives[1])
		}
	})
}
