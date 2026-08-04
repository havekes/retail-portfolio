---
name: ticket-execution
description: Use when executing a planned work ticket (a GitHub issue labeled "ticket") — branch/worktree setup, following the issue's ## Plan section, commit style, running builds and tests, addressing PR review feedback, and opening the pull request with gh.
---

# Ticket Execution

Turn one planned ticket into one clean pull request. The issue's `## Plan` section tells you **how** — your job is to execute it faithfully and verify every acceptance criterion.

## 1. Set up

- Read the issue completely with `gh issue view <N> --comments`: objective, scope, acceptance criteria, `## Plan` (your contract for the how), `## Review feedback` (present on respawns), and `## Technical notes`.
- If the issue body has **no `## Plan` section or it is empty**, stop and report back — the ticket-planning step was skipped; the orchestrator must run it first.
- The branch name is in the issue's `## Meta` section (`branch:`). Base work on current `main`:
  - Sequential run (main checkout): `git fetch origin && git checkout -b <branch> origin/main`
  - Parallel run (orchestrator assigned a worktree): use `scripts/setup-agent-worktree.sh <worktree-path> <branch>` (which creates the worktree and a dynamic `.env`), then `cd <worktree-path> && docker compose up -d`, and work **only inside that worktree's isolated containers**. If you were spawned with an isolated worktree workspace by `invoke_subagent`, use that workspace instead and ensure the unique `.env` logic is applied before running `docker compose up -d`.
- Never commit on `main`.

## 2. Execute the plan

- Follow the plan's ordered steps and file list. It maps to the acceptance criteria — don't skip steps.
- If reality diverged since planning (code moved, a dependency merged differently), deviate **minimally** and record every deviation for the PR body.
- Stay inside the ticket's **In scope**. Respect **Out of scope** literally — a plan step that drifts out of scope is a red flag, not an invitation.
- Follow existing project conventions (read neighboring code first). Match the stack in `PROJECT.md`: Go backend, SvelteKit + Tailwind + shadcn-svelte frontend, SQLite.
- Small, coherent commits with imperative messages (`Add receipt schema migrations`, `Wire upload endpoint to vision pipeline`).
- If review feedback exists: address every finding, or justify the exception in the PR body.

## 3. Verify

Before opening the PR, run the relevant checks and make them pass:

- Go: `go build ./... && go test ./...` (and `go vet ./...` when touching Go)
- Frontend: the project's lint/build commands (e.g. `npm run check`, `npm run build`)
- Every acceptance criterion: verify it concretely (run it, query it, or test it — not by inspection). The plan's **Verification** section is your checklist.

## 4. Open the PR

```
gh pr create --title "<TICKET-ID>: <ticket title>" --body <body>
```

PR body template:

```markdown
## Ticket
<TICKET-ID> — <title> (Refs #<issue-number>)

## What changed
- <bullet per logical change>

## Acceptance criteria verification
- [x] <criterion> — <how it was verified: command/test/output>

## Plan deviations
<Omit if none. One bullet per deviation from the ticket's ## Plan and why reality required it.>

## Review feedback addressed
<Omit on first submission. On respawn: one bullet per finding → how it was addressed, or why not.>

## Out of scope / follow-ups
<Anything discovered but deliberately not done. Omit if empty.>
```

Use `Refs #<issue-number>`, not `Closes` — the orchestrator closes the issue after merge.

## 5. Report back

Final message to the orchestrator with: branch name, PR URL, implementation summary (bullets), exact verification commands + results, out-of-scope observations. Do not touch the issue's labels or close it — the orchestrator owns state.

## Never

- No merges, no force-push, no rebasing onto anything but `origin/main`, no edits to other issues or their labels.
- No unrequested refactors of code outside the ticket's blast radius.
- No re-planning on the fly: if the plan is fundamentally wrong (not just stale), report back instead of silently rewriting the approach.
