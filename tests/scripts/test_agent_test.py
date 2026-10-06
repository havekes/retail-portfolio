"""Regression tests for the ``scripts/agent-test`` harness.

The harness is an extension-less Python script, so it cannot be imported through
``sys.path``. It is loaded hermetically with ``SourceFileLoader`` and driven with
stubbed runners, report files (in ``tmp_path``) and report paths. No Docker, no
network, no external services.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "agent-test"

ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"

UNHANDLED_ERROR = "Error: Unhandled error during test run"


def load_harness() -> ModuleType:
    """Load ``scripts/agent-test`` as a module without touching ``sys.path``."""
    name = "agent_test_harness_under_test"
    loader = SourceFileLoader(name, str(HARNESS_PATH))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through ``sys.modules`` during exec.
    sys.modules[name] = module
    try:
        loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    return load_harness()


def write_vitest_report(path: Path, *, failing: bool) -> None:
    """Write a minimal vitest JSON report shaped for ``parse_vitest()``."""
    assertions = [
        {
            "status": "passed",
            "fullName": f"suite > passes {index}",
            "title": f"passes {index}",
            "failureMessages": [],
        }
        for index in range(3 if not failing else 2)
    ]
    if failing:
        assertions.append(
            {
                "status": "failed",
                "fullName": "suite > fails",
                "title": "fails",
                "failureMessages": ["AssertionError: expected 1 to be 2"],
            }
        )
    failed = sum(1 for assertion in assertions if assertion["status"] == "failed")
    payload = {
        "numTotalTestSuites": 1,
        "numTotalTests": len(assertions),
        "numPassedTests": len(assertions) - failed,
        "numFailedTests": failed,
        "numPendingTests": 0,
        "numTodoTests": 0,
        "testResults": [
            {
                "name": "/app/src/lib/example.test.ts",
                "status": "failed" if failing else "passed",
                "assertionResults": assertions,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@dataclass
class StubProc:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class StubRunner:
    """Runner double that materialises a report before returning ``proc``."""

    def __init__(self, proc: StubProc, report: Path, *, failing: bool) -> None:
        self.proc = proc
        self.report = report
        self.failing = failing

    def run(self, ecosystem: str, args: list[str], timeout: int = 3600) -> StubProc:  # noqa: ARG002
        write_vitest_report(self.report, failing=self.failing)
        return self.proc


def run_with(
    harness: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    returncode: int,
    failing: bool,
    stdout: str = "",
    stderr: str = "",
):
    report = tmp_path / "frontend.json"
    monkeypatch.setattr(
        harness,
        "report_path",
        lambda ecosystem, name, local: (report, str(report)),
    )
    runner = StubRunner(
        StubProc(returncode=returncode, stdout=stdout, stderr=stderr),
        report,
        failing=failing,
    )
    result = harness.run_tests(
        runner, "frontend", [], fail_fast=False, coverage=False, local=True
    )
    return runner, result


def test_run_tests_flags_nonzero_exit_with_clean_report(
    harness: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exit 1 with a fully-parsed, clean report must be a command failure."""
    noise = "\n".join(f"noise line {index:03d}" for index in range(200))
    stdout = (
        f"{noise}\n"
        f"{ANSI_RED}{UNHANDLED_ERROR}{ANSI_RESET}\n"
        "    at node_modules/vitest/dist/chunks/worker.js:1:1\n"
        "FAIL  src/lib/example.test.ts > suite\n"
    )
    _, result = run_with(
        harness,
        monkeypatch,
        tmp_path,
        returncode=1,
        failing=False,
        stdout=stdout,
        stderr=f"{ANSI_RED}Error: boom{ANSI_RESET}\n",
    )

    assert result.total == 3
    assert result.command_failed is True
    assert result.note.startswith("runner exited 1\n")
    assert UNHANDLED_ERROR in result.note
    assert "Error: boom" in result.note
    assert "node_modules" not in result.note
    assert "\x1b" not in result.note
    # Only the sanitized tail is kept: the note is the prefix plus 800 chars.
    assert len(result.note) == len("runner exited 1\n") + 800
    assert "noise line 000" not in result.note
    # AC 3: the guarded result must never render the silent-success line.
    index = harness.render_index([result])
    assert "All tests passed." not in index
    assert "! runner exited 1" in index


def test_run_tests_not_flagged_when_failures_parsed(
    harness: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A report that already accounts for exit 1 must not be double-reported."""
    _, result = run_with(
        harness,
        monkeypatch,
        tmp_path,
        returncode=1,
        failing=True,
        stdout=UNHANDLED_ERROR,
    )

    assert result.failed == 1
    assert result.failures
    assert result.command_failed is False
    assert result.note == ""
    # Genuine parsed failures keep the Index rendering byte-for-byte unchanged.
    assert harness.render_index([result]) == (
        "INDEX\n"
        "  frontend (full): 2 passed, 1 failed\n"
        "  Failed (frontend):\n"
        "    frontend/src/lib/example.test.ts\n"
        "      - suite > fails"
    )


def test_run_tests_ignores_zero_exit(
    harness: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A clean report with exit 0 stays a passing run."""
    _, result = run_with(
        harness, monkeypatch, tmp_path, returncode=0, failing=False, stdout="ok"
    )

    assert result.total == 3
    assert result.command_failed is False
    assert result.note == ""


def test_render_index_no_passed_when_command_failed(harness: ModuleType) -> None:
    """A command failure must suppress the silent-success "All tests passed." line."""
    failed_result = harness.Result(
        ecosystem="frontend",
        mode="full",
        total=3,
        passed=3,
        command_failed=True,
        note="runner exited 1\nError: Unhandled error during test run",
    )

    index = harness.render_index([failed_result])

    assert "All tests passed." not in index
    assert "! runner exited 1" in index

    healthy_result = harness.Result(
        ecosystem="frontend", mode="full", total=3, passed=3
    )
    assert "All tests passed." in harness.render_index([healthy_result])
