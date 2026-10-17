package httpapi

import (
	"log/slog"
	"net/http"
)

// NewRouter constructs the http.ServeMux with registered handlers wrapped with TraceMiddleware and LoggingMiddleware.
func NewRouter(logger *slog.Logger) http.Handler {
	if logger == nil {
		logger = slog.Default()
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", HealthHandler)
	mux.HandleFunc("/compute", ComputeHandler)
	return TraceMiddleware(LoggingMiddleware(logger)(mux))
}
