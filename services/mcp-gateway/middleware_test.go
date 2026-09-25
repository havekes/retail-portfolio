package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type flusherRecorder struct {
	*httptest.ResponseRecorder
	flushed bool
}

func (f *flusherRecorder) Flush() {
	f.flushed = true
}

func TestLoggingResponseWriter_BasicsAndFlusher(t *testing.T) {
	rec := &flusherRecorder{
		ResponseRecorder: httptest.NewRecorder(),
	}
	lrw := newLoggingResponseWriter(rec)

	if lrw.statusCode != http.StatusOK {
		t.Fatalf("expected initial status 200, got %d", lrw.statusCode)
	}
	if lrw.Unwrap() != rec {
		t.Fatalf("expected Unwrap to return underlying writer")
	}

	lrw.WriteHeader(http.StatusTeapot)
	if lrw.statusCode != http.StatusTeapot {
		t.Fatalf("expected status %d, got %d", http.StatusTeapot, lrw.statusCode)
	}

	// Secondary WriteHeader should not overwrite statusCode
	lrw.WriteHeader(http.StatusOK)
	if lrw.statusCode != http.StatusTeapot {
		t.Fatalf("expected status to remain %d, got %d", http.StatusTeapot, lrw.statusCode)
	}

	n, err := lrw.Write([]byte("test payload"))
	if err != nil || n != 12 {
		t.Fatalf("unexpected Write result: n=%d, err=%v", n, err)
	}
	if lrw.bytesWritten != 12 {
		t.Fatalf("expected 12 bytes written, got %d", lrw.bytesWritten)
	}

	lrw.Flush()
	if !rec.flushed {
		t.Fatalf("expected underlying flusher to be called")
	}
}

func TestLoggingResponseWriter_NonFlusher(t *testing.T) {
	// A plain struct that does not implement http.Flusher
	rec := httptest.NewRecorder()
	lrw := newLoggingResponseWriter(rec)
	// Calling Flush should not panic when underlying writer is not a Flusher
	lrw.Flush()
}

func TestLoggingMiddleware_InboundRequests(t *testing.T) {
	paths := []string{"/health", "/mcp"}

	for _, path := range paths {
		t.Run("path_"+path, func(t *testing.T) {
			var buf bytes.Buffer
			logger, err := newLogger(&buf, "prod", "INFO")
			if err != nil {
				t.Fatalf("newLogger error: %v", err)
			}
			prev := setSlogDefault(logger)
			defer setSlogDefault(prev)

			client := mustClient(t, "http://backend.invalid", "test-token", "prod")
			server := newMCPServer(client, Config{Environment: "prod"})
			router := newRouter(server)
			handler := loggingMiddleware(router, "prod")

			req := httptest.NewRequest(http.MethodGet, path, nil)
			req.RemoteAddr = "192.168.1.100:12345"
			rec := httptest.NewRecorder()

			handler.ServeHTTP(rec, req)

			out := buf.String()
			if out == "" {
				t.Fatalf("expected log output for %s, got empty", path)
			}

			var entry map[string]any
			for _, line := range strings.Split(strings.TrimSpace(out), "\n") {
				var parsed map[string]any
				if err := json.Unmarshal([]byte(line), &parsed); err == nil {
					if parsed["msg"] == "http request" {
						entry = parsed
						break
					}
				}
			}

			if entry == nil {
				t.Fatalf("expected 'http request' log entry for %s, got:\n%s", path, out)
			}

			if entry["method"] != http.MethodGet {
				t.Errorf("expected method GET, got %v", entry["method"])
			}
			if entry["path"] != path {
				t.Errorf("expected path %s, got %v", path, entry["path"])
			}
			if entry["remote_addr"] != "192.168.1.100:12345" {
				t.Errorf("expected remote_addr 192.168.1.100:12345, got %v", entry["remote_addr"])
			}
			if _, ok := entry["status"]; !ok {
				t.Errorf("expected status in log entry, got %v", entry)
			}
			if _, ok := entry["duration"]; !ok {
				t.Errorf("expected duration in log entry, got %v", entry)
			}
		})
	}
}

func TestLoggingMiddleware_DevAndRedaction(t *testing.T) {
	t.Run("dev logs details with redacted sensitive headers", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "dev", "DEBUG")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		var capturedBody string
		targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			b, _ := io.ReadAll(r.Body)
			capturedBody = string(b)
			w.WriteHeader(http.StatusOK)
		})

		handler := loggingMiddleware(targetHandler, "dev")

		reqBody := `{"symbol":"AAPL"}`
		req := httptest.NewRequest(http.MethodPost, "/test?debug=1", strings.NewReader(reqBody))
		req.Header.Set("Authorization", "Bearer super-secret-auth-token")
		req.Header.Set("X-Service-Token", "super-secret-service-token")
		req.Header.Set("Cookie", "session=super-secret-cookie")
		req.Header.Set("Set-Cookie", "tracker=super-secret-tracker")
		req.Header.Set("Accept", "application/json")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		if capturedBody != reqBody {
			t.Fatalf("handler did not receive original body: %q", capturedBody)
		}

		out := buf.String()
		if !strings.Contains(out, "incoming http request") {
			t.Fatalf("expected dev mode to log 'incoming http request', got:\n%s", out)
		}
		if !strings.Contains(out, "debug=1") {
			t.Errorf("expected log to contain query debug=1, got:\n%s", out)
		}
		if !strings.Contains(out, "body=") || !strings.Contains(out, "AAPL") {
			t.Errorf("expected log to contain request body, got:\n%s", out)
		}

		// Ensure sensitive tokens are redacted
		if strings.Contains(out, "super-secret-auth-token") {
			t.Errorf("log leaked Authorization header value")
		}
		if strings.Contains(out, "super-secret-service-token") {
			t.Errorf("log leaked X-Service-Token header value")
		}
		if strings.Contains(out, "super-secret-cookie") {
			t.Errorf("log leaked Cookie header value")
		}
		if strings.Contains(out, "super-secret-tracker") {
			t.Errorf("log leaked Set-Cookie header value")
		}
		if !strings.Contains(out, "[REDACTED]") {
			t.Errorf("expected '[REDACTED]' in log output, got:\n%s", out)
		}
	})

	t.Run("prod suppresses debug request details", func(t *testing.T) {
		var buf bytes.Buffer
		logger, err := newLogger(&buf, "prod", "INFO")
		if err != nil {
			t.Fatalf("newLogger error: %v", err)
		}
		prev := setSlogDefault(logger)
		defer setSlogDefault(prev)

		targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
		})

		handler := loggingMiddleware(targetHandler, "prod")

		req := httptest.NewRequest(http.MethodPost, "/test?debug=1", strings.NewReader(`{"symbol":"AAPL"}`))
		req.Header.Set("Authorization", "Bearer secret")
		rec := httptest.NewRecorder()

		handler.ServeHTTP(rec, req)

		out := buf.String()
		if strings.Contains(out, "incoming http request") {
			t.Fatalf("prod mode should not emit 'incoming http request', got:\n%s", out)
		}
		if strings.Contains(out, "DEBUG") {
			t.Fatalf("prod mode should not emit DEBUG logs, got:\n%s", out)
		}
		if strings.Contains(out, "AAPL") {
			t.Fatalf("prod mode should not dump request body, got:\n%s", out)
		}
	})
}

func TestLoggingMiddleware_ProviderNameCompliance(t *testing.T) {
	var buf bytes.Buffer
	logger, err := newLogger(&buf, "dev", "DEBUG")
	if err != nil {
		t.Fatalf("newLogger error: %v", err)
	}
	prev := setSlogDefault(logger)
	defer setSlogDefault(prev)

	targetHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := loggingMiddleware(targetHandler, "dev")
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	assertNoProviderName(t, "middleware log", buf.String())
}

// setSlogDefault sets slog's default logger and returns a restore function.
func setSlogDefault(logger *slog.Logger) *slog.Logger {
	prev := slog.Default()
	slog.SetDefault(logger)
	return prev
}
