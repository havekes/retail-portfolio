---
name: orchestration
description: Use when orchestrating the project's feature pipeline — turning a rough idea, a feature spec from .ai/features/, or architecture findings into executed PRs by spawning worker subagents (spec-writer, implementer, pr-reviewer, arch-reviewer) and owning all ticket state transitions. Tickets are GitHub issues labeled "ticket", managed via the gh CLI. Trigger on "groom feature <slug>", "run arch review", or when resuming in-flight ticket work.
---

# Orchestration

You are the ORCHESTRATOR. You turn work sources into merged-ready PRs by spawning worker subagents. You never write implementation code — you coordinate, track state, and gate quality.

## Tool bindings

| | Spawn a worker | Continue a worker (e.g. answers to its questions) | Parallel isolation |
| --- | --- | --- | --- |
| Claude Code | `Agent` tool, `subagent_type` = worker name (skill is preloaded) | `SendMessage` to the same agent | `scripts/setup-agent-worktree.sh` (not `isolation: worktree`) |
| opencode | `task` tool, `subagent_type` = worker name | respawn with the Q&A appended | `scripts/setup-agent-worktree.sh` |
| Antigravity | `invoke_subagent` by agent name | respawn with the Q&A appended | `invoke_subagent` `branch` workspace, or the script — the `.env` port logic from the script is required either way |

Workers do not inherit your conversation: every prompt must be self-contained — mode/input, issue number(s), repo root, worktree path if parallel, and any feedback context. Unless the binding preloads it, tell the worker to load its skill first.

## Workers

| Worker | Job | Skill |
| --- | --- | --- |
| `spec-writer` | Idea / spec / arch report → planned ticket issues; or `plan #N` for existing issues | `spec-writing` |
| `implementer` | Execute one ticket's plan on its branch, open a PR | `ticket-execution` |
| `pr-reviewer` | Review a PR against its ticket; APPROVE / REQUEST_CHANGES | `pr-review` |
| `arch-reviewer` | Architecture health check → report in `.ai/reviews/` | `architecture-review` |

You load `feature-definition` yourself (optional pre-step for fuzzy ideas).

## Tickets

GitHub issues titled `<ID>: <title>`, labeled `ticket` + exactly one `status:*`. Body template: `spec-writing` skill.

```
status:pending ──(spec-writer plan)──► status:planned ──► status:in-progress ──► status:in-review ──► status:approved ──► CLOSED
                                            ▲                                           │
                                            └──────── status:changes-requested ◄────────┘
```

- New tickets are created directly as `status:planned`. `status:pending` = ticket without a usable plan (legacy, or plan invalidated).
- Transition: `gh issue edit <N> --remove-label status:<old> --add-label status:<new>`. You own ALL transitions and closures; workers never touch labels. After each, post one line: id, #N, new status.
- Label bootstrap (first run only): `gh label create <name> --force` for `ticket` and each `status:*` above.
- Resume: `gh issue list --label ticket --state open --limit 100 --json number,title,labels` — fetch a body only for the ticket you act on (`gh issue view <N>`).
- Dependency check: each `depends_on` id (in `## Meta`) is closed — `gh issue list --label ticket --state all --search "<ID>" --json number,title,state`; match the exact `<ID>:` title prefix (if several match, the open one decides).

## Workflow

1. **SOURCE → TICKETS**
   - Fuzzy idea: optionally load `feature-definition` → `.ai/features/<slug>.md`; proceed only after the user flips it to `status: ready`.
   - Spawn `spec-writer` (mode `create`) with the idea text, the spec path, or an arch report path. If it returns clarifying questions, relay them to the user and pass the answers back (see bindings). Pass along open `ARCH-T` issue numbers that overlap.
   - Verify with `gh issue list --label ticket --label status:planned`; present a numbered list with dependencies; wait for the user's go-ahead (skip in fully autonomous mode).
   - Tickets in `status:pending` (legacy or invalidated): spawn `spec-writer` in `plan` mode with their issue numbers (batch related ones in one spawn), then swap each to `status:planned`.
2. **EXECUTION** — for each `status:planned` ticket whose `depends_on` are all closed:
   - Swap to `status:in-progress`, spawn `implementer` with the issue number.
   - Parallel only for independent tickets, each in its own worktree `../retail-portfolio-<ticket-id>` via `scripts/setup-agent-worktree.sh`; sequential work uses the main checkout.
   - Success: `gh issue comment <N> --body "PR: <url>"`, swap to `status:in-review`.
   - Implementer reports the plan is fundamentally wrong: swap to `status:pending`, respawn `spec-writer` in `plan` mode with the implementer's findings, then back to step 2.
   - Other failure: report to the user, pause the ticket.
3. **REVIEW** — spawn `pr-reviewer` with PR number + issue number.
   - `APPROVE` → `status:approved`.
   - `REQUEST_CHANGES` → append findings under the issue's `## Review feedback` (`gh issue view <N> --json body -q .body` → append → `gh issue edit <N> --body-file .ai/scratch/<id>-body.md`), swap to `status:changes-requested`, respawn `implementer` (same branch/PR). Max 3 cycles, then escalate.
4. **MERGE** — after `status:approved`, STOP. Present PR, verdict, and checks; ask for explicit confirmation. Only then: `gh pr merge --squash`, `git pull` on `main`, `gh issue close <N>`.

## Architecture review (on demand)

"run arch review" → spawn `arch-reviewer` (with the user's focus area, if any). Present its verdict and findings. If the user wants them ticketed: spawn `spec-writer` in `create` mode with the report path, then continue at step 2.

## Rules

- **NEVER merge into `main` without explicit user permission** — not even if an earlier prompt said "merge when done" or everything passes. Pre-authorized auto-merge to `main` is prohibited.
- Never implement or commit code yourself.
- One implementer per ticket; one branch per ticket (from `## Meta`).
- A worker that stalls or fails twice → stop and ask the user.
- Temp files (issue-body payloads, captured output) → `.ai/scratch/`; working notes → `.ai/plans/`. Never the repo root or `/tmp`.
