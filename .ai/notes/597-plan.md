## Plan

**Approach:**
Shrink `services/mcp-gateway/backendclient.go` to pass `json.RawMessage` through for pass-through tools (`Prices`, `SymbolSearch`, `OptionsChain`, and `Fundamentals`), deleting ~75 lines of redundant mirrored structs (`PriceBar`, `PriceHistory`, `SymbolLookupResult`, `OptionsContract`, `OptionsGreeks`, `OptionsQuote`, `OptionsChainEntry`, `OptionsChain`). Retain typed models only for the three projection tools (`CompanyProfile`, `KeyMetrics`, `FinancialRatios`, `CompanyFundamentals`) and statement items, and relax statement decoding by removing `DisallowUnknownFields` from `decodeStatementItems` so new backend fields degrade gracefully instead of failing statement tools at runtime.
Rejected alternative: Dropping typed models completely and using dynamic JSON traversal for projection tools was rejected because typed structs in Go ensure strict output shaping and schema clarity for projections without brittle key navigation.

**Files:**
- `services/mcp-gateway/backendclient.go` — modify: change return types of `Prices`, `SymbolSearch`, `OptionsChain`, and `Fundamentals` to `(json.RawMessage, error)`; delete 8 unused struct definitions; remove `decoder.DisallowUnknownFields()` in `decodeStatementItems`.
- `services/mcp-gateway/tools.go` — modify: update projection tools (`get_key_metrics`, `get_financial_ratios`, `get_company_details`) to unmarshal raw fundamentals into `CompanyFundamentals` before returning projected fields.
- `services/mcp-gateway/backendclient_test.go` — modify: update `TestBackendClientDecodesRealBackendShapes` subtests for prices, options chain, and fundamentals to assert raw JSON pass-through semantics; add assertion verifying extra backend statement fields are tolerated.
- `services/mcp-gateway/tools_test.go` — modify: update assertions for `get_price_history`, `get_options_chain`, and `search_symbols` to decode into generic maps/structs; update `TestDecodeStatementListFieldSetContract` to verify lenient decoding with unknown fields while preserving date/symbol header checks.

**Steps:**
1. Update `services/mcp-gateway/backendclient.go` method signatures and struct definitions:
   - Change `Prices`, `SymbolSearch`, `OptionsChain`, and `Fundamentals` signatures to return `(json.RawMessage, error)`.
   - Remove obsolete mirrored structs: `PriceBar`, `PriceHistory`, `SymbolLookupResult`, `OptionsContract`, `OptionsGreeks`, `OptionsQuote`, `OptionsChainEntry`, `OptionsChain`.
   - In `decodeStatementItems`, remove `decoder.DisallowUnknownFields()`, allowing lenient decoding where unknown fields are ignored. Retain required `date` and `symbol` checks in `decodeStatementList`.
2. Update `services/mcp-gateway/tools.go` projection tool handlers:
   - Add helper `decodeFundamentals(raw json.RawMessage) (CompanyFundamentals, error)` unmarshaling raw bytes into `CompanyFundamentals`.
   - Update `get_key_metrics`, `get_financial_ratios`, and `get_company_details` handlers to decode raw fundamentals and return `fundamentals.KeyMetrics`, `fundamentals.Ratios`, and `fundamentals.Profile` respectively.
   - Leave `get_fundamentals`, `get_price_history`, `get_options_chain`, and `search_symbols` to pass raw messages directly to `runTool` -> `successResult`.
3. Update `services/mcp-gateway/backendclient_test.go`:
   - In `TestBackendClientDecodesRealBackendShapes`:
     - Update "prices" subtest to assert `Prices` returns valid `json.RawMessage` containing expected fields (`symbol`, `items`).
     - Update "options chain" subtest to assert `OptionsChain` returns valid `json.RawMessage` containing expected fields (`underlying_symbol`, `contracts`).
     - Update "fundamentals" subtest to assert `Fundamentals` returns valid `json.RawMessage` that can be unmarshaled into `CompanyFundamentals`.
     - Update or add a statement test case verifying that unknown/extra fields in backend statement payloads decode without error.
4. Update `services/mcp-gateway/tools_test.go`:
   - In `TestTools_Success`:
     - Update `get_price_history` assert function to unmarshal into a generic map or anonymous struct rather than deleted `PriceHistory`.
     - Update `get_options_chain` assert function to unmarshal into a generic map or anonymous struct rather than deleted `OptionsChain`.
     - Update `search_symbols` assert function to unmarshal into `[]map[string]any` rather than deleted `[]SymbolLookupResult`.
     - Verify `get_fundamentals`, `get_key_metrics`, `get_financial_ratios`, and `get_company_details` tests continue to pass and assert correct projections.
   - In `TestDecodeStatementListFieldSetContract`:
     - Add test case verifying that unknown fields (e.g. `{"date": "2024-09-28", "symbol": "AAPL", "custom_line_item": "100"}`) decode cleanly without error.
     - Remove or update the obsolete `cross-statement payload fails` test that depended on `DisallowUnknownFields`, retaining header checks (`missing header fields fails`) and `unknown statement fails`.
5. Run test suite and linters:
   - Run `cd services/mcp-gateway && go test -v ./...`.
   - Run `cd services/mcp-gateway && go vet ./...`.
   - Run provider-name compliance tests: `cd services/mcp-gateway && go test -v -run Compliance ./...`.
   - Check line count diff in `backendclient.go` to confirm net reduction in hand-mirrored struct lines.

**Verification:**
- Criterion 1 (backend statement/api_types field addition no longer causes runtime failure):
  - Run `cd services/mcp-gateway && go test -v -run "TestDecodeStatementListFieldSetContract|TestBackendClientDecodesRealBackendShapes" .` — passes, verifying lenient decode tolerates unknown fields.
- Criterion 2 (projection tools still return correctly shaped projections):
  - Run `cd services/mcp-gateway && go test -v -run TestTools_Success .` — passes, verifying `get_key_metrics`, `get_financial_ratios`, and `get_company_details` return expected projection fields.
- Criterion 3 (TestBackendClientDecodesRealBackendShapes / TestDecodeStatementListFieldSetContract updated to new decode semantics):
  - Inspect `services/mcp-gateway/backendclient_test.go` and `services/mcp-gateway/tools_test.go` and run both tests — all subtests pass under new semantics.
- Criterion 4 (net reduction in hand-mirrored struct lines in backendclient.go):
  - Run `git diff --stat services/mcp-gateway/backendclient.go` and verify net negative line count (~75 lines removed).
- Criterion 5 (all go test, go vet green; provider-name compliance tests pass):
  - Run `cd services/mcp-gateway && go test ./... && go vet ./...` (passes with 0 errors).
  - Run `cd services/mcp-gateway && go test -v -run Compliance ./...` (all compliance tests pass).

**Risks / watch-outs:**
- Corrupt JSON responses: If the backend returns a 200 OK with malformed JSON, `c.get`'s `json.Unmarshal(body, out)` handles it by classifying as `ErrProvider` ("malformed response from the market data service") before passing to tools. For projection tools, unmarshaling `json.RawMessage` into `CompanyFundamentals` also returns a clear error handled by `runTool`.
- Preserving date/symbol validation on statements: Relaxing `DisallowUnknownFields` removes strict field set checking, but the explicit `date` and `symbol` non-empty checks in `decodeStatementList` ensure essential header identity is still verified before returning results to agents.
