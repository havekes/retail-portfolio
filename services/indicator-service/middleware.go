package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"net"
	"net/http"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

// requestIDHeader carries the correlation id between the backend and this
// service, and back to the caller.
const requestIDHeader = "X-Request-ID"

// requestIDKey is the context key for the request correlation id.
type requestIDKey struct{}

// RequestIDFromContext returns the request id stored on ctx, or "".
func RequestIDFromContext(ctx context.Context) string {
	if id, ok := ctx.Value(requestIDKey{}).(string); ok {
		return id
	}
	return ""
}

// withRequestID stores id on ctx for RequestIDFromContext.
func withRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, requestIDKey{}, id)
}

// newRequestID generates a random correlation id.
func newRequestID() string {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return ""
	}
	return hex.EncodeToString(buf)
}

// statusResponseWriter records the response status code (for the request span)
// and keeps the underlying writer's optional interfaces available.
type statusResponseWriter struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
}

func (w *statusResponseWriter) WriteHeader(code int) {
	if !w.wroteHeader {
		w.status = code
		w.wroteHeader = true
	}
	w.ResponseWriter.WriteHeader(code)
}

func (w *statusResponseWriter) Write(b []byte) (int, error) {
	if !w.wroteHeader {
		w.status = http.StatusOK
		w.wroteHeader = true
	}
	return w.ResponseWriter.Write(b)
}

// Status returns the status code sent to the client, defaulting to 200 when
// the handler wrote a body without calling WriteHeader.
func (w *statusResponseWriter) Status() int {
	if !w.wroteHeader {
		return http.StatusOK
	}
	return w.status
}

// Flush forwards to the underlying writer when it supports flushing.
func (w *statusResponseWriter) Flush() {
	if !w.wroteHeader {
		w.status = http.StatusOK
		w.wroteHeader = true
	}
	if flusher, ok := w.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

// Hijack forwards to the underlying writer when it supports hijacking.
func (w *statusResponseWriter) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	if hijacker, ok := w.ResponseWriter.(http.Hijacker); ok {
		return hijacker.Hijack()
	}
	return nil, nil, http.ErrNotSupported
}

// RequestIDMiddleware honours an inbound X-Request-ID (generating one when
// absent), echoes it on the response and stores it on the request context.
func RequestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := r.Header.Get(requestIDHeader)
		if requestID == "" {
			requestID = newRequestID()
		}
		w.Header().Set(requestIDHeader, requestID)
		next.ServeHTTP(w, r.WithContext(withRequestID(r.Context(), requestID)))
	})
}

// TraceMiddleware continues an inbound traceparent and produces the server span
// for the request. The span is set on the request context so handler spans
// become its children.
func TraceMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		statusWriter := &statusResponseWriter{ResponseWriter: w}

		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		ctx, span := tracer().Start(
			ctx,
			r.Method+" "+r.URL.Path,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				attribute.String("http.method", r.Method),
				attribute.String("http.route", r.URL.Path),
			),
		)
		defer func() {
			span.SetAttributes(attribute.Int("http.status_code", statusWriter.Status()))
			span.End()
		}()

		next.ServeHTTP(statusWriter, r.WithContext(ctx))
	})
}
