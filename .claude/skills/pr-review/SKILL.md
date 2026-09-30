---
name: pr-review
description: Use when reviewing a pull request that implements a ticket (a GitHub issue labeled "ticket"). Provides the review checklist (acceptance criteria, correctness, scope, tests, security, conventions) and the APPROVE / REQUEST_CHANGES verdict format.
---

# PR Review

The ticket's acceptance criteria are the contract. Read-only: never modify code, issues, or PRs.

## Inputs

- Ticket: `gh issue view <N> --comments` (criteria, plan, review history).
- PR: `gh pr view <P>`, `gh pr diff <P>`, `gh pr checks <P>`.

Read the diff first, then only the surrounding code needed to judge it (callers, callees, neighboring tests) — not whole modules. Don't re-run tests locally; CI (`gh pr checks`) is the source of truth. Pending checks → say so in Notes. Failing checks → `blocker`.

## Checklist

1. **Acceptance criteria** — each is demonstrably met by the diff. Missing criterion = `blocker`.
2. **Correctness** — logic errors, edge cases, error handling (no swallowed exceptions; no unhandled promise rejections), transactions around multi-table writes.
3. **Scope** — only what the ticket scoped; unrelated changes are `scope` findings for a follow-up.
4. **Tests** — new behavior covered, or the PR body shows concrete verification. Untested critical path ≥ `major`. Any test hitting a real external service (Redis, HTTP, SMTP, frontend API) = `major`.
5. **Security** — injection, missing input validation, secrets, unsafe file handling, path traversal.
6. **Fit** — matches `AGENTS.md` / area-guide conventions; model changes ship a migration; API shapes match what dependent tickets' plans expect.
7. **Plan deviations** — each listed deviation is justified; unlisted ones are findings.
8. **Clarity** — naming and structure. Don't nitpick what tooling owns.

## Severity

`blocker` (broken, unsafe, fails criteria) · `major` (real defect, missing critical coverage) · `minor` (apply now) · `nit` (optional).
Any `blocker`/`major` → REQUEST_CHANGES. Otherwise APPROVE, listing the rest as follow-ups.

## Output (your entire final message)

```
VERDICT: APPROVE | REQUEST_CHANGES

## Findings
1. [severity] file:line — <issue> → <concrete fix>

## Criteria check
- [x]/[ ] <each acceptance criterion>

## Notes
<Scope observations, follow-up ideas, pending checks. Omit if empty.>
```

Self-contained: the orchestrator pastes findings into the issue and the implementer works from them alone. No persistent files; any captured notes go to `.ai/scratch/`.
