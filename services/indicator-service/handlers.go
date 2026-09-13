package main

import (
	"encoding/json"
	"net/http"
)

// HealthHandler handles GET /health requests.
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		_ = json.NewEncoder(w).Encode(ErrorResponse{Error: "method not allowed"})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(HealthResponse{
		Status:  "ok",
		Service: "indicator-service",
	})
}

// ComputeHandler handles POST /compute requests.
func ComputeHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		_ = json.NewEncoder(w).Encode(ErrorResponse{Error: "method not allowed"})
		return
	}

	w.Header().Set("Content-Type", "application/json")

	// Limit body size to 10MB
	r.Body = http.MaxBytesReader(w, r.Body, 10<<20)

	var req ComputeRequest
	dec := json.NewDecoder(r.Body)
	dec.UseNumber()
	if err := dec.Decode(&req); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(ErrorResponse{Error: "invalid json body: " + err.Error()})
		return
	}

	resp := ComputeResponse{
		Indicators: make(map[string]any),
	}

	interval := req.Interval
	if interval == "" {
		interval = "1d"
	}

	for _, spec := range req.Indicators {
		result, err := ComputeIndicator(req.Candles, spec, interval)
		if err != nil {
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(ErrorResponse{Error: err.Error()})
			return
		}
		resp.Indicators[spec.ResultKey()] = result
	}

	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

// NewRouter constructs the http.ServeMux with registered handlers.
func NewRouter() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", HealthHandler)
	mux.HandleFunc("/compute", ComputeHandler)
	return mux
}
