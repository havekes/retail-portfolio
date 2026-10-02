package main

import (
	"bytes"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

// sensitiveHeaders lists HTTP header names that must be redacted in logs.
var sensitiveHeaders = map[string]bool{
	"authorization":   true,
	"x-service-token": true,
	"cookie":          true,
	"set-cookie":      true,
}

// sanitizeHeaders returns a copy of headers with sensitive values replaced by "[REDACTED]".
func sanitizeHeaders(headers http.Header) map[string][]string {
	sanitized := make(map[string][]string, len(headers))
	for k, v := range headers {
		lower := strings.ToLower(k)
		if sensitiveHeaders[lower] {
			sanitized[k] = []string{"[REDACTED]"}
		} else {
			vals := make([]string, len(v))
			copy(vals, v)
			sanitized[k] = vals
		}
	}
	return sanitized
}

// loggingResponseWriter captures the HTTP status code and bytes written.
type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int64
	written      bool
}

func newLoggingResponseWriter(w http.ResponseWriter) *loggingResponseWriter {
	return &loggingResponseWriter{
		ResponseWriter: w,
		statusCode:     http.StatusOK,
	}
}

func (rw *loggingResponseWriter) WriteHeader(code int) {
	if !rw.written {
		rw.statusCode = code
		rw.written = true
	}
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *loggingResponseWriter) Write(b []byte) (int, error) {
	if !rw.written {
		rw.written = true
	}
	n, err := rw.ResponseWriter.Write(b)
	rw.bytesWritten += int64(n)
	return n, err
}

// Flush implements http.Flusher by delegating to the underlying writer if supported.
func (rw *loggingResponseWriter) Flush() {
	if f, ok := rw.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// Unwrap returns the underlying http.ResponseWriter.
func (rw *loggingResponseWriter) Unwrap() http.ResponseWriter {
	return rw.ResponseWriter
}

// loggingMiddleware returns an http.Handler that logs incoming requests and durations.
func loggingMiddleware(next http.Handler, env string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		var bodyBytes []byte
		if isDev(env) && r.Body != nil && r.Body != http.NoBody {
			var err error
			bodyBytes, err = io.ReadAll(io.LimitReader(r.Body, 64<<10))
			_ = r.Body.Close()
			r.Body = io.NopCloser(bytes.NewReader(bodyBytes))
			if err != nil {
				slog.DebugContext(r.Context(), "failed to read request body for logging", slog.String("error", err.Error()))
			}
		}

		if isDev(env) {
			slog.DebugContext(r.Context(), "incoming http request",
				slog.String("method", r.Method),
				slog.String("path", r.URL.Path),
				slog.Any("headers", sanitizeHeaders(r.Header)),
				slog.String("query", r.URL.RawQuery),
				slog.String("body", string(bodyBytes)),
			)
		}

		rw := newLoggingResponseWriter(w)
		next.ServeHTTP(rw, r)

		duration := time.Since(start)
		slog.InfoContext(r.Context(), "http request",
			slog.String("method", r.Method),
			slog.String("path", r.URL.Path),
			slog.String("remote_addr", r.RemoteAddr),
			slog.Int("status", rw.statusCode),
			slog.Duration("duration", duration),
		)
	})
}
