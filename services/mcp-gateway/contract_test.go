package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

type openAPIDoc struct {
	OpenAPI    string                           `json:"openapi"`
	Info       openAPIInfo                      `json:"info"`
	Paths      map[string]map[string]openAPIOperation `json:"paths"`
	Components map[string]any                   `json:"components"`
}

type openAPIInfo struct {
	Title   string `json:"title"`
	Version string `json:"version"`
}

type openAPIOperation struct {
	Summary     string             `json:"summary"`
	OperationID string             `json:"operationId"`
	Parameters  []openAPIParameter `json:"parameters"`
}

type openAPIParameter struct {
	Name     string         `json:"name"`
	In       string         `json:"in"`
	Required bool           `json:"required"`
	Schema   map[string]any `json:"schema"`
}

// findContractPath resolves the path to data_plane_openapi.json from the
// current working directory, relative candidates, or upward traversal.
func findContractPath(t *testing.T) string {
	t.Helper()
	candidates := []string{
		"../../tests/market/contracts/data_plane_openapi.json",
		"../tests/market/contracts/data_plane_openapi.json",
		"tests/market/contracts/data_plane_openapi.json",
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			abs, err := filepath.Abs(c)
			if err == nil {
				return abs
			}
			return c
		}
	}

	// Fall back to traversing upward from current working directory
	dir, err := os.Getwd()
	if err == nil {
		for {
			candidate := filepath.Join(dir, "tests", "market", "contracts", "data_plane_openapi.json")
			if _, err := os.Stat(candidate); err == nil {
				return candidate
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}

	t.Fatalf("could not find data_plane_openapi.json in any expected candidate paths")
	return ""
}

func loadOpenAPIContract(t *testing.T) *openAPIDoc {
	t.Helper()
	contractPath := findContractPath(t)
	data, err := os.ReadFile(contractPath)
	if err != nil {
		t.Fatalf("failed reading OpenAPI contract at %q: %v", contractPath, err)
	}

	var doc openAPIDoc
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatalf("failed unmarshaling OpenAPI contract at %q: %v", contractPath, err)
	}
	return &doc
}

func matchPath(template, actual string) bool {
	tmplParts := strings.Split(strings.Trim(template, "/"), "/")
	actParts := strings.Split(strings.Trim(actual, "/"), "/")
	if len(tmplParts) != len(actParts) {
		return false
	}
	for i := range tmplParts {
		if strings.HasPrefix(tmplParts[i], "{") && strings.HasSuffix(tmplParts[i], "}") {
			if actParts[i] == "" {
				return false
			}
			continue
		}
		if tmplParts[i] != actParts[i] {
			return false
		}
	}
	return true
}

func validateRequest(doc *openAPIDoc, req *http.Request) (string, error) {
	if req.Header.Get(serviceTokenHeader) == "" {
		return "", fmt.Errorf("%s header missing or empty", serviceTokenHeader)
	}

	var matchedTemplate string
	for tmpl := range doc.Paths {
		if matchPath(tmpl, req.URL.Path) {
			matchedTemplate = tmpl
			break
		}
	}
	if matchedTemplate == "" {
		return "", fmt.Errorf("request path %q does not match any OpenAPI path in contract", req.URL.Path)
	}

	op, ok := doc.Paths[matchedTemplate][strings.ToLower(req.Method)]
	if !ok {
		return matchedTemplate, fmt.Errorf("method %s not defined for path %s in OpenAPI contract", req.Method, matchedTemplate)
	}

	allowedQuery := make(map[string]bool)
	requiredQuery := make(map[string]bool)

	for _, param := range op.Parameters {
		if param.In == "query" {
			allowedQuery[param.Name] = true
			if param.Required {
				requiredQuery[param.Name] = true
			}
		}
	}

	queryValues := req.URL.Query()
	for paramName := range queryValues {
		if !allowedQuery[paramName] {
			return matchedTemplate, fmt.Errorf("query parameter %q sent to %s is not defined in OpenAPI contract", paramName, matchedTemplate)
		}
	}

	for reqParam := range requiredQuery {
		if queryValues.Get(reqParam) == "" {
			return matchedTemplate, fmt.Errorf("required query parameter %q missing in request to %s", reqParam, matchedTemplate)
		}
	}

	return matchedTemplate, nil
}

func TestOpenAPIContractArtifactExistsAndValid(t *testing.T) {
	doc := loadOpenAPIContract(t)

	if !strings.HasPrefix(doc.OpenAPI, "3.") {
		t.Errorf("expected openapi 3.x, got %q", doc.OpenAPI)
	}
	if doc.Info.Title != "Market Data Plane Contract" {
		t.Errorf("expected title 'Market Data Plane Contract', got %q", doc.Info.Title)
	}
	if doc.Info.Version != "1.0.0" {
		t.Errorf("expected version '1.0.0', got %q", doc.Info.Version)
	}

	expectedRoutes := []string{
		"/api/v1/market/data/prices/{symbol}",
		"/api/v1/market/data/symbols/search",
		"/api/v1/market/data/options/{symbol}",
		"/api/v1/market/data/fundamentals/{symbol}",
		"/api/v1/market/data/fundamentals/{symbol}/statements",
	}

	if len(doc.Paths) != len(expectedRoutes) {
		t.Errorf("expected %d paths, got %d", len(expectedRoutes), len(doc.Paths))
	}

	for _, route := range expectedRoutes {
		ops, ok := doc.Paths[route]
		if !ok {
			t.Errorf("expected route %q in contract paths", route)
			continue
		}
		getOp, ok := ops["get"]
		if !ok {
			t.Errorf("expected GET operation on route %q", route)
			continue
		}
		if getOp.OperationID == "" {
			t.Errorf("expected non-empty operationId for GET %q", route)
		}
	}
}

func TestBackendClientOpenAPIParity(t *testing.T) {
	doc := loadOpenAPIContract(t)

	exercisedRoutes := make(map[string]int)
	var mu sync.Mutex

	stub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		matchedRoute, err := validateRequest(doc, r)
		if err != nil {
			t.Errorf("contract validation error on %s %s: %v", r.Method, r.URL.String(), err)
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		mu.Lock()
		exercisedRoutes[matchedRoute]++
		mu.Unlock()

		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.Contains(r.URL.Path, "/prices/"):
			_, _ = w.Write([]byte(`{"symbol":"AAPL","exchange":"US","from_date":"2024-01-01","to_date":"2024-01-02","items":[]}`))
		case strings.Contains(r.URL.Path, "/symbols/search"):
			_, _ = w.Write([]byte(`[]`))
		case strings.Contains(r.URL.Path, "/options/"):
			_, _ = w.Write([]byte(`{"underlying_symbol":"AAPL","as_of":"2024-01-01","contracts":[]}`))
		case strings.HasSuffix(r.URL.Path, "/statements"):
			_, _ = w.Write([]byte(`[]`))
		case strings.Contains(r.URL.Path, "/fundamentals/"):
			_, _ = w.Write([]byte(`{"profile":{"symbol":"AAPL","company_name":"Apple Inc."}}`))
		default:
			_, _ = w.Write([]byte(`{}`))
		}
	}))
	t.Cleanup(stub.Close)

	client := mustClient(t, stub.URL, "valid-service-token")
	ctx := context.Background()

	// 1. Prices (with and without optional exchange)
	from := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	to := time.Date(2024, 1, 10, 0, 0, 0, 0, time.UTC)
	if _, err := client.Prices(ctx, "AAPL", from, to, "US"); err != nil {
		t.Fatalf("Prices with exchange failed: %v", err)
	}
	if _, err := client.Prices(ctx, "AAPL", from, to, ""); err != nil {
		t.Fatalf("Prices without exchange failed: %v", err)
	}

	// 2. SymbolSearch
	if _, err := client.SymbolSearch(ctx, "Apple"); err != nil {
		t.Fatalf("SymbolSearch failed: %v", err)
	}

	// 3. OptionsChain (with all filters, and with nil filters)
	expiry := time.Date(2025, 1, 17, 0, 0, 0, 0, time.UTC)
	strikeMin := 100.0
	strikeMax := 200.0
	if _, err := client.OptionsChain(ctx, "AAPL", &expiry, "call", &strikeMin, &strikeMax); err != nil {
		t.Fatalf("OptionsChain with filters failed: %v", err)
	}
	if _, err := client.OptionsChain(ctx, "AAPL", nil, "", nil, nil); err != nil {
		t.Fatalf("OptionsChain without filters failed: %v", err)
	}

	// 4. Fundamentals (with and without exchange)
	if _, err := client.Fundamentals(ctx, "AAPL", "US"); err != nil {
		t.Fatalf("Fundamentals with exchange failed: %v", err)
	}
	if _, err := client.Fundamentals(ctx, "AAPL", ""); err != nil {
		t.Fatalf("Fundamentals without exchange failed: %v", err)
	}

	// 5. Statements (with all parameters, and with minimal)
	if _, err := client.Statements(ctx, "AAPL", "income", "annual", 5, "US"); err != nil {
		t.Fatalf("Statements with all parameters failed: %v", err)
	}
	if _, err := client.Statements(ctx, "AAPL", "balance", "", 0, ""); err != nil {
		t.Fatalf("Statements minimal failed: %v", err)
	}

	// Assert 100% of the OpenAPI contract routes were exercised
	for route := range doc.Paths {
		count := exercisedRoutes[route]
		if count == 0 {
			t.Errorf("contract route %q was never exercised by BackendClient methods", route)
		}
	}
	if len(exercisedRoutes) != len(doc.Paths) {
		t.Errorf("expected %d distinct routes exercised, got %d", len(doc.Paths), len(exercisedRoutes))
	}
}

func TestBackendClientOpenAPINegativeDrift(t *testing.T) {
	doc := loadOpenAPIContract(t)

	cases := []struct {
		name        string
		url         string
		headerToken string
		wantErrMsg  string
	}{
		{
			name:        "missing service token header",
			url:         "/api/v1/market/data/prices/AAPL?from=2024-01-01&to=2024-01-02",
			headerToken: "",
			wantErrMsg:  "X-Service-Token header missing",
		},
		{
			name:        "unknown route",
			url:         "/api/v1/market/data/unknown/route",
			headerToken: "test-token",
			wantErrMsg:  "does not match any OpenAPI path",
		},
		{
			name:        "missing required query param 'to' on prices",
			url:         "/api/v1/market/data/prices/AAPL?from=2024-01-01",
			headerToken: "test-token",
			wantErrMsg:  "required query parameter \"to\" missing",
		},
		{
			name:        "missing required query param 'from' on prices",
			url:         "/api/v1/market/data/prices/AAPL?to=2024-01-02",
			headerToken: "test-token",
			wantErrMsg:  "required query parameter \"from\" missing",
		},
		{
			name:        "missing required query param 'q' on search",
			url:         "/api/v1/market/data/symbols/search",
			headerToken: "test-token",
			wantErrMsg:  "required query parameter \"q\" missing",
		},
		{
			name:        "missing required query param 'statement' on statements",
			url:         "/api/v1/market/data/fundamentals/AAPL/statements",
			headerToken: "test-token",
			wantErrMsg:  "required query parameter \"statement\" missing",
		},
		{
			name:        "unknown query param on prices",
			url:         "/api/v1/market/data/prices/AAPL?from=2024-01-01&to=2024-01-02&unknown_foo=1",
			headerToken: "test-token",
			wantErrMsg:  "query parameter \"unknown_foo\" sent to /api/v1/market/data/prices/{symbol} is not defined",
		},
		{
			name:        "unknown query param on search",
			url:         "/api/v1/market/data/symbols/search?q=AAPL&bad_param=val",
			headerToken: "test-token",
			wantErrMsg:  "query parameter \"bad_param\" sent to /api/v1/market/data/symbols/search is not defined",
		},
		{
			name:        "unknown query param on options",
			url:         "/api/v1/market/data/options/AAPL?unexpected=val",
			headerToken: "test-token",
			wantErrMsg:  "query parameter \"unexpected\" sent to /api/v1/market/data/options/{symbol} is not defined",
		},
		{
			name:        "unknown query param on fundamentals",
			url:         "/api/v1/market/data/fundamentals/AAPL?bogus=val",
			headerToken: "test-token",
			wantErrMsg:  "query parameter \"bogus\" sent to /api/v1/market/data/fundamentals/{symbol} is not defined",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req, err := http.NewRequest(http.MethodGet, tc.url, nil)
			if err != nil {
				t.Fatalf("failed to construct request: %v", err)
			}
			if tc.headerToken != "" {
				req.Header.Set(serviceTokenHeader, tc.headerToken)
			}

			_, err = validateRequest(doc, req)
			if err == nil {
				t.Fatalf("expected error containing %q, got nil", tc.wantErrMsg)
			}
			if !strings.Contains(err.Error(), tc.wantErrMsg) {
				t.Fatalf("expected error containing %q, got: %v", tc.wantErrMsg, err)
			}
		})
	}
}
