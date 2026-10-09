---
name: ticket-execution
description: Use when executing a planned work ticket (a GitHub issue labeled "ticket") — branch/worktree setup, following the issue's ## Plan section, commits, verification with ./scripts/agent-test, addressing PR review feedback, and opening the pull request with gh.
---

# Ticket Execution

Turn one planned ticket into one clean PR. The issue's `## Plan` is your contract for the **how**; the acceptance criteria are the contract for the **what**.

## 1. Set up

- `gh issue view <N> --comments`: objective, scope, acceptance criteria, `## Plan`, `## Technical notes`, `## Review feedback` (on respawns).
- `## Plan` missing or empty → stop and report; the orchestrator must get it planned first.
- Branch = `branch:` in `## Meta`, based on `origin/<base>` (the `base:` feature branch; legacy tickets without `base:` use `main`).
  - Main checkout: `git fetch origin && git checkout -b <branch> origin/<base>` (respawn: `git checkout <branch>`).
  - Parallel run: `scripts/setup-agent-worktree.sh <worktree-path> <branch> origin/<base>`, then `cd <worktree-path> && docker compose up -d`; work and run every command **only** inside that worktree (its `.env` isolates ports and the compose project). If your tool gave you an isolated workspace instead, still apply the script's `.env` logic before `docker compose up -d`.
- Legacy paths in old issues: `.agent/<dir>/…` / `.opencode/<dir>/…` now live at `.ai/<dir>/…`.
- Read the area guide for what you touch: `src/AGENTS.md` (backend) and/or `frontend/AGENTS.md`.
- Never commit on `main` or on the base branch.

## 2. Execute

- Follow the plan's steps and file list in order.
- The plan was written before its dependencies merged. If reality diverged (moved code, different upstream contract), deviate **minimally** and record each deviation for the PR body. If the plan is fundamentally wrong, stop and report — don't silently re-plan.
- Stay inside **In scope**; treat **Out of scope** literally. No drive-by refactors.
- Match neighboring code. Backend model change ⇒ generate the Alembic migration (`docker compose exec backend uv run alembic revision --autogenerate -m "<msg>"`).
- Small, coherent commits, imperative subjects (`Add receipt schema migration`).
- Review feedback present: address every finding, or justify the exception in the PR body.

## 3. Verify

All checks run through the harness (Docker-backed, output capped):

- While iterating: `./scripts/agent-test <test file>` (fail-fast, one target).
- Before the PR: `./scripts/agent-test` — Gate 0 (lint + types) then full regression for the touched ecosystems. Must pass.
- Each acceptance criterion: verify concretely per the plan's **Verification** (run/test/query — not by inspection).
- Tests mock all outbound I/O (Redis, HTTP, SMTP; frontend API calls).

## 4. Open the PR

`gh pr create --base <base> --title "<ID>: <ticket title>" --body-file .ai/scratch/<id>-pr.md`

```markdown
## Ticket
<ID> — <title> (Refs #<issue>)

## What changed
- <per logical change>

## Acceptance criteria verification
- [x] <criterion> — <how verified>

## Plan deviations
<Omit if none.>

## Review feedback addressed
<Omit on first submission. Per finding → fix, or why not.>

## Out of scope / follow-ups
<Omit if none.>
```

Use `Refs #N`, never `Closes` — the orchestrator closes after merge. On respawn, push to the same branch; the PR updates.

## 5. Report back

Final message: branch, PR URL, what was implemented (bullets), plan deviations, verification commands + results, out-of-scope observations.

## Never

- Merge, force-push, rebase onto anything but `origin/<base>`, or touch issue labels/state.
- Leave temp files outside `.ai/scratch/` (of the checkout you work in). No other persistent local files — branch, commits, and PR are the output.
