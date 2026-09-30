## Plan

**Approach:** Narrow the guard in `run_tests()` (`scripts/agent-test:440`) from `proc.returncode not in (0, 1) and result.total == 0` to any non-zero exit combined with a report that has no failed/errored test cases, and carry the sanitized tail of runner output into `note` in that branch. Cover it with the first-ever automated test for the harness: load `scripts/agent-test` as a Python module (it is a plain Python file without a `.py` extension, #!/usr/bin/env python3), drive `run_tests()` with a stub `Runner` + stubbed `report_path()`, and assert on both `Result.command_failed/note` and `render_index()` output. No script refactor needed — the existing dataclasses (`Runner`, `Result` at `scripts/agent-test:107-118`) are already a sufficient seam.

**Files:**
- `scripts/agent-test` — modify: exit-detection guard in `run_tests()` (currently lines 440–443).
- `tests/scripts/test_agent_test.py` — create: regression tests for the guard and the summary rendering.

**Steps:**
1. In `run_tests()` (`scripts/agent-test:413-444`), replace the guard at line 440 with: flag `result.command_failed = True` when `proc.returncode != 0` **and** `result.failed == 0 and result.errors == 0 and len(result.failures) == 0` (i.e., the parsed report does not already account for the failure). Drop the `total == 0` clause and the `(0, 1)` exception entirely. This satisfies:
   - exit 1 with a fully-passing vitest JSON report → `command_failed` (the PR #645 silent-success case),
   - still no flag when exit 1 comes from genuine parsed test failures (report accounts for them),
   - still no flag on exit 0.
   In the flagged branch, keep building `note` as sanitization + truncation of runner output, applied regardless of `proc.returncode`: `tail = sanitize(proc.stdout + "\n" + proc.stderr, ecosystem)[-800:]` and `result.note = result.note or f"runner exited {proc.returncode}\n{tail}"` (signature reuse of existing `sanitize(text, ecosystem)` at `scripts/agent-test:171`).
2. Create `tests/scripts/test_agent_test.py` that imports the module hermetically via `importlib.util.spec_from_file_location("agent_test", REPO_ROOT / "scripts" / "agent-test")` — no repo mutation, no Docker, no external services.
3. Write `test_run_tests_flags_nonzero_exit_with_clean_report()`: stub `report_path` (monkeypatch on the loaded module) to return `(tmp_path / "frontend.json", str(tmp_path / "frontend.json"))`; a fake `Runner.run(ecosystem, cmd)` writes a minimal vitest JSON report (e.g. `{"numTotalTests": 3, "numPassedTests": 3, "testResults": [{"assertionResults": [...], "status": "passed"}]}` matching what `parse_vitest()` at `scripts/agent-test:380` reads) into that path and returns a short `CompletedProcess`-shaped object with `returncode=1` plus sample stdout/stderr containing an ANSI sequence and a vendor line (e.g. `node_modules/foo`). Assert: `result.command_failed is True`, `result.total == 3`, and `result.note` contains the (sanitized, ≤800-char) tail — the ANSI codes stripped, the error text present.
4. Write the mirror test `test_run_tests_not_flagged_when_failures_parsed()`: same fake report but with 1 failing assertion and exit code 1; assert `result.command_failed is False` (keeps byte-for-byte Index/Traces behavior — no double-reporting as a command failure).
5. Write `test_render_index_no_passed_when_command_failed()`: build `Result(ecosystem="frontend", mode="full", total=3, passed=3, command_failed=True, note="runner exited 1\nError: unhandled dispatch")` and assert `"All tests passed." not in render_index([result])` (guards the silent-success branch at `scripts/agent-test:508-509`). Also assert the happy path: the same result without `command_failed`/`note` still renders `"All tests passed."`.
6. Run the new tests via `./scripts/agent-test tests/scripts/test_agent_test.py` (targeted, fail-fast), then full `./scripts/agent-test` for the backend ecosystem; confirm Gate 0 (ruff + ty) passes on both the modified script and the new test file, and that CI on this branch runs the new test.

**Verification:**
- `./scripts/agent-test tests/scripts/test_agent_test.py` — 3 tests pass; Index line shows `backend (targeted): 3 passed` (no `command_failed` surprises).
- AC 1 (non-zero exit + no failed/errored tests → `command_failed`, regardless of `total`): covered by step 1 change, asserted in step 3 (`total == 3`, exit 1, clean report → flagged).
- AC 2 (`note` includes sanitized, length-capped runner tail): asserted in step 3 (ANSI stripped, output capped at 800 chars).
- AC 3 (exit 1 with 0 parsed failures does NOT print "All tests passed."): asserted in step 5 via `render_index()` with `command_failed=True` — the `note` lines (step 1) feed `render_index`'s `! note` path via the failure branch at `scripts/agent-test:475-476`.
- AC 4 (genuine parsed failure unchanged): asserted in step 4 — `command_failed` stays `False`; remaining Index/Traces rendering untouched.
- AC 5: full `./scripts/agent-test --backend` (Gate 0 + suite) clean.

**Risks / watch-outs:**
- pytest also exits 1 when tests fail and 2 for collection errors; the "report accounts for it" condition (failed/errors/tests-parsed) must be checked, not just exit code, or legit failing runs would be double-reported. Collection errors (exit 2) typically produce a `errors > 0` or `total == 0` report — with 0 failures the result is now flagged as command_failed, which is the desired loud behavior (old code only caught this when `total == 0`; coverage for pytest mid-run errors stays identical otherwise).
- Importing a file without `.py` extension needs `SourceFileLoader`/`spec_from_file_location` (not plain `sys.path` import); the test must handle that explicitly. Run the tests with `-x`/agent-test targeted mode to see quick failures since the module import is the fragile first step.
- `run_tests()` writes/removes the host report file (`scripts/agent-test:425-426`); the test's stubbed `report_path` must point into `tmp_path` to stay hermetic and avoid clobbering real `.cache/agent-test` files.
- Scope guard: only the ~440 Guard + rolling `note` + tests — do not touch parsers, gate0, or report format (per Out of scope).
