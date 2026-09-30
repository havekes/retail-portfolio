## Plan

**Approach:**
Slice FastAPI's OpenAPI document to the five `/api/v1/market/data` routes using `fastapi.openapi.utils.get_openapi` and check it in as `tests/market/contracts/data_plane_openapi.json`. Enforce parity symmetrically: a Python backend test (`tests/market/test_data_plane_contract.py`) regenerates from the live `src.main.app` and fails on diff, while a Go contract test (`services/mcp-gateway/contract_test.go`) loads the artifact and asserts `BackendClient` paths, query-param names, and required params match the snapshot.
Rejected alternative: Checking in a full backend OpenAPI document leaks unrelated domain schemas (auth, portfolios, accounts) and forces artifact updates when unrelated routes change; slicing strictly to `/api/v1/market/data` isolates data-plane changes.

**Files:**
- `src/market/openapi.py` — create: extract `/api/v1/market/data` routes from FastAPI app and generate the sliced OpenAPI contract dict with CLI regeneration support.
- `tests/market/contracts/data_plane_openapi.json` — create: committed OpenAPI 3.1 artifact containing the 5 data-plane routes and their referenced component schemas.
- `tests/market/test_data_plane_contract.py` — create: backend test that regenerates OpenAPI schema from the live app, verifies route coverage, and fails if the committed artifact drifts.
- `services/mcp-gateway/contract_test.go` — create: Go test that loads `data_plane_openapi.json`, invokes `BackendClient` methods against `httptest.Server`, and validates route paths, query-param names, and required parameters against OpenAPI.
- `services/mcp-gateway/README.md` — modify: update the "Backend data plane" section and endpoint table to link to `tests/market/contracts/data_plane_openapi.json` as the source of truth.

**Steps:**
1. Create `src/market/openapi.py`:
   - Implement `get_data_plane_openapi(app: FastAPI | None = None) -> dict[str, Any]` that filters `app.routes` for paths starting with `/api/v1/market/data` and calls `fastapi.openapi.utils.get_openapi` with title `"Market Data Plane Contract"` and version `"1.0.0"`.
   - Add a CLI main entry point (`if __name__ == "__main__":`) that formats JSON with `indent=2, sort_keys=True` and writes to `tests/market/contracts/data_plane_openapi.json`.
2. Generate and commit `tests/market/contracts/data_plane_openapi.json`:
   - Run the generator to produce the initial artifact covering all 5 data-plane routes (`/prices/{symbol}`, `/symbols/search`, `/options/{symbol}`, `/fundamentals/{symbol}`, `/fundamentals/{symbol}/statements`) and their Pydantic schemas.
3. Implement backend contract test `tests/market/test_data_plane_contract.py`:
   - Add `test_data_plane_openapi_artifact_matches_live_fastapi`: compares live `get_data_plane_openapi()` output with `tests/market/contracts/data_plane_openapi.json`. Supports `UPDATE_CONTRACTS=1` env var to regenerate. Fails with a clear diff if live routes/parameters change without updating the artifact.
   - Add `test_data_plane_contract_covers_all_five_routes`: asserts the 5 data-plane routes are present in `paths` and no unexpected routes leaked in.
   - Add `test_data_plane_contract_parameters`: asserts expected query params and types exist for each route.
4. Implement Go contract test `services/mcp-gateway/contract_test.go`:
   - Implement helper `findContractPath(t *testing.T) string` that resolves `tests/market/contracts/data_plane_openapi.json` from `services/mcp-gateway` (or repo root / parent search).
   - Implement `TestOpenAPIContractArtifactExistsAndValid` parsing the artifact into typed OpenAPI Go structs.
   - Implement `TestBackendClientOpenAPIParity` running a stub `httptest.Server` and calling all `BackendClient` methods (`Prices`, `SymbolSearch`, `OptionsChain`, `Fundamentals`, `Statements`):
     - Validates request path matches OpenAPI path template.
     - Validates all query parameter names sent by `BackendClient` are defined in OpenAPI for that route.
     - Validates all required OpenAPI query parameters are provided.
     - Validates `X-Service-Token` header is sent.
     - Validates that 100% of the 5 OpenAPI routes are exercised.
   - Implement negative drift test case asserting that missing required params or sending unknown query params causes a contract test failure.
5. Update `services/mcp-gateway/README.md`:
   - Update the "Backend data plane" section and endpoint contract table to explicitly link to `tests/market/contracts/data_plane_openapi.json` as the committed source of truth.
6. Verify and run quality checks:
   - Run backend tests: `uv run pytest tests/market/test_data_plane_contract.py`.
   - Run Go tests: `cd services/mcp-gateway && go test -v ./...`.
   - Run linters: `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `cd services/mcp-gateway && go vet ./...`.

**Verification:**
- Criterion 1 (OpenAPI artifact exists covering all five routes):
  - Inspect `tests/market/contracts/data_plane_openapi.json` — verify valid JSON containing `/prices/{symbol}`, `/symbols/search`, `/options/{symbol}`, `/fundamentals/{symbol}`, `/fundamentals/{symbol}/statements`.
- Criterion 2 (Backend test fails on route/param drift):
  - Run `uv run pytest tests/market/test_data_plane_contract.py` (passes).
  - Verify that altering a parameter in `data_router.py` causes `test_data_plane_openapi_artifact_matches_live_fastapi` to fail with a diff.
- Criterion 3 (Go test fails when `backendclient.go` paths/params drift):
  - Run `cd services/mcp-gateway && go test -v -run TestBackendClientOpenAPIParity .` (passes).
  - Verify that altering a query parameter name in `backendclient.go` causes `TestBackendClientOpenAPIParity` to fail.
- Criterion 4 (README links to artifact as source of truth):
  - Inspect `services/mcp-gateway/README.md` and confirm relative markdown link to `tests/market/contracts/data_plane_openapi.json` works and documents the artifact as source of truth.

**Risks / watch-outs:**
- Path resolution in Go tests: Go tests run in `services/mcp-gateway/`, while CI may invoke them from root or subfolder. `findContractPath` must check `../../tests/market/contracts/data_plane_openapi.json` and `tests/market/contracts/data_plane_openapi.json`, falling back to traversing upward.
- Deterministic JSON formatting: `get_data_plane_openapi` must serialize with `indent=2, sort_keys=True` to guarantee reproducible diffs across test runs and environments.
