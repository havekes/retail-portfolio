package main

import (
	"encoding/json"
	"log/slog"
	"net/http"
)

// HealthHandler handles GET /health requests.
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		reqID := RequestIDFromContext(r.Context())
		logger := LoggerFromContext(r.Context())
		logger.Warn("method not allowed",
			slog.String("request_id", reqID),
			slog.String("path", r.URL.Path),
			slog.String("error", "method not allowed"),
		)
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
	reqID := RequestIDFromContext(r.Context())
	logger := LoggerFromContext(r.Context())

	if r.Method != http.MethodPost {
		logger.Warn("method not allowed",
			slog.String("request_id", reqID),
			slog.String("path", r.URL.Path),
			slog.String("error", "method not allowed"),
		)
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
		logger.Error("malformed json payload",
			slog.String("request_id", reqID),
			slog.String("path", r.URL.Path),
			slog.String("error", err.Error()),
		)
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
			logger.Error("indicator calculation failed",
				slog.String("request_id", reqID),
				slog.String("path", r.URL.Path),
				slog.String("error", err.Error()),
			)
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(ErrorResponse{Error: err.Error()})
			return
		}
		resp.Indicators[spec.ResultKey()] = result
	}

	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(resp)
}

// NewRouter constructs the http.ServeMux with registered handlers wrapped with LoggingMiddleware.
func NewRouter(loggers ...*slog.Logger) http.Handler {
	var logger *slog.Logger
	if len(loggers) > 0 && loggers[0] != nil {
		logger = loggers[0]
	} else {
		logger = slog.Default()
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", HealthHandler)
	mux.HandleFunc("/compute", ComputeHandler)
	return LoggingMiddleware(logger)(mux)
}
