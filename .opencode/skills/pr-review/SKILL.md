---
name: pr-review
description: Use when reviewing a pull request that implements a ticket (a GitHub issue labeled "ticket"). Provides the review checklist (correctness, acceptance criteria, scope, tests, security, conventions) and the APPROVE / REQUEST_CHANGES verdict format.
---

# PR Review

Review the PR against its ticket — the ticket's acceptance criteria are the contract.

## Inputs

- Ticket's GitHub issue number: `gh issue view <N> --comments` (objective, scope, acceptance criteria, review history).
- PR number: `gh pr view <N>`, `gh pr diff <N>`, `gh pr checks <N>`.

## Checklist

1. **Acceptance criteria** — every box in the ticket is demonstrably satisfied by the diff. Missing criterion = automatic REQUEST_CHANGES.
2. **Correctness** — logic errors, off-by-ones, error handling (no swallowed exceptions in Python; no unhandled promise rejections in TS), transaction boundaries where writes span multiple tables.
3. **Scope discipline** — diff contains only what the ticket scoped. Flag unrelated changes as `scope` findings (they belong in a follow-up ticket).
4. **Tests/verification** — new behavior is covered or the PR body shows concrete verification. Untested critical paths = at least a `major`.
5. **Security & data safety** — SQL injection, missing input validation on endpoints, secrets in code, unsafe file handling (upload endpoint!), path traversal.
6. **Conventions & fit** — matches existing project patterns and the PROJECT.md stack; migrations are idempotent/auto-applied as the blueprint requires; API shapes match what later frontend tickets will consume.
7. **Clarity** — names, structure, comments where non-obvious. Don't nitpick style that tooling should own.

## Severity levels

- `blocker` — broken, unsafe, or fails acceptance criteria.
- `major` — real defect or missing test coverage on a critical path.
- `minor` — improvement the author should apply now.
- `nit` — optional.

Verdict rule: any `blocker` or `major` → REQUEST_CHANGES. Only `minor`/`nit` → APPROVE (list them as follow-up suggestions).

## Output format (your entire final message)

```
VERDICT: APPROVE | REQUEST_CHANGES

## Findings
1. [severity] file:line — <issue> → <concrete suggested fix>
2. ...

## Criteria check
- [x]/[ ] <each acceptance criterion from the ticket>

## Notes
<Anything the orchestrator should know: scope observations, follow-up ticket ideas. Omit if empty.>
```

Be specific and self-contained — the orchestrator pastes your findings into the ticket and the implementer works from them without seeing this conversation.
