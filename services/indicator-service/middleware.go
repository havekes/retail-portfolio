package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

type contextKey string

const (
	requestIDKey contextKey = "request_id"
	loggerKey    contextKey = "logger"
)

// RequestIDFromContext extracts the request ID from the context if present.
func RequestIDFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if v, ok := ctx.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

// LoggerFromContext extracts the logger from the context if present,
// falling back to slog.Default().
func LoggerFromContext(ctx context.Context) *slog.Logger {
	if ctx == nil {
		return slog.Default()
	}
	if l, ok := ctx.Value(loggerKey).(*slog.Logger); ok && l != nil {
		return l
	}
	return slog.Default()
}

// WithRequestID returns a new context with the provided request ID attached.
func WithRequestID(ctx context.Context, reqID string) context.Context {
	return context.WithValue(ctx, requestIDKey, reqID)
}

// WithLogger returns a new context with the provided logger attached.
func WithLogger(ctx context.Context, logger *slog.Logger) context.Context {
	return context.WithValue(ctx, loggerKey, logger)
}

// generateRequestID generates an RFC 4122 version 4 UUID string.
func generateRequestID() string {
	var b [16]byte
	_, err := rand.Read(b[:])
	if err != nil {
		return fmt.Sprintf("req-%d", time.Now().UnixNano())
	}
	b[6] = (b[6] & 0x0f) | 0x40 // Version 4
	b[8] = (b[8] & 0x3f) | 0x80 // Variant 10xx (RFC 4122)
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// statusResponseWriter wraps http.ResponseWriter to capture the HTTP status code.
type statusResponseWriter struct {
	http.ResponseWriter
	statusCode int
	written    bool
}

func newStatusResponseWriter(w http.ResponseWriter) *statusResponseWriter {
	return &statusResponseWriter{
		ResponseWriter: w,
		statusCode:     http.StatusOK,
	}
}

func (rw *statusResponseWriter) WriteHeader(statusCode int) {
	if !rw.written {
		rw.statusCode = statusCode
		rw.written = true
	}
	rw.ResponseWriter.WriteHeader(statusCode)
}

func (rw *statusResponseWriter) Write(b []byte) (int, error) {
	if !rw.written {
		rw.written = true
	}
	return rw.ResponseWriter.Write(b)
}

// Unwrap returns the underlying http.ResponseWriter.
func (rw *statusResponseWriter) Unwrap() http.ResponseWriter {
	return rw.ResponseWriter
}

// LoggingMiddleware creates an HTTP middleware that logs request details,
// propagates or generates an X-Request-ID, tracks latency, and binds a scoped
// logger into the request context.
func LoggingMiddleware(logger *slog.Logger) func(http.Handler) http.Handler {
	if logger == nil {
		logger = slog.Default()
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			reqID := strings.TrimSpace(r.Header.Get("X-Request-ID"))
			if reqID == "" {
				reqID = generateRequestID()
			}
			w.Header().Set("X-Request-ID", reqID)

			scopedLogger := logger.With(slog.String("request_id", reqID))
			ctx := WithRequestID(r.Context(), reqID)
			ctx = WithLogger(ctx, scopedLogger)
			r = r.WithContext(ctx)

			var bodyBytes []byte
			if logger.Enabled(r.Context(), slog.LevelDebug) && r.Body != nil && r.Body != http.NoBody {
				var err error
				bodyBytes, err = io.ReadAll(io.LimitReader(r.Body, 10<<20))
				_ = r.Body.Close()
				r.Body = io.NopCloser(bytes.NewReader(bodyBytes))
				if err != nil {
					scopedLogger.Debug("failed to read request body for logging", slog.String("error", err.Error()))
				}
			}

			rw := newStatusResponseWriter(w)
			start := time.Now()

			next.ServeHTTP(rw, r)

			duration := time.Since(start)
			durationMs := duration.Milliseconds()

			if logger.Enabled(r.Context(), slog.LevelDebug) {
				attrs := []slog.Attr{
					slog.String("method", r.Method),
					slog.String("path", r.URL.Path),
					slog.Int("status", rw.statusCode),
					slog.Int64("duration_ms", durationMs),
					slog.Duration("duration", duration),
					slog.String("remote_addr", r.RemoteAddr),
					slog.String("request_id", reqID),
				}
				if len(bodyBytes) > 0 && r.URL.Path == "/compute" {
					attrs = append(attrs, slog.String("body", string(bodyBytes)))
				}
				logger.LogAttrs(r.Context(), slog.LevelDebug, "http request", attrs...)
			} else {
				attrs := []slog.Attr{
					slog.String("method", r.Method),
					slog.String("path", r.URL.Path),
					slog.Int("status", rw.statusCode),
					slog.Int64("duration_ms", durationMs),
					slog.Duration("duration", duration),
					slog.String("remote_addr", r.RemoteAddr),
					slog.String("request_id", reqID),
				}

				var level slog.Level
				switch {
				case rw.statusCode >= 500:
					level = slog.LevelError
				case rw.statusCode >= 400:
					level = slog.LevelWarn
				default:
					level = slog.LevelInfo
				}

				logger.LogAttrs(r.Context(), level, "http request", attrs...)
			}
		})
	}
}
