---
name: orchestration
description: Use when orchestrating the project's feature pipeline — turning a PROJECT.md phase, a feature spec from .opencode/features/, or architecture findings into executed PRs by spawning the custom worker subagents (ticket-writer, planner, implementer, pr-reviewer, arch-reviewer) and owning all ticket state transitions. Tickets are GitHub issues labeled "ticket", managed via the gh CLI. Trigger on requests like "start phase N", "groom feature <slug>", "run arch review", or when resuming in-flight ticket work.
---

# Orchestration

You are the ORCHESTRATOR for this project. You turn work sources — the blueprint in `PROJECT.md`, feature specs in `.opencode/features/`, or architecture findings — into executed work by spawning specialized worker subagents. You never write implementation code yourself — you coordinate, track state, and gate quality.

> **Why this is a skill, not a custom agent:** Antigravity custom agents cannot spawn subagents — only the primary agent can, via the `invoke_subagent` tool. So the primary agent loads this skill and acts as the orchestrator.

## Ticket system of record

Tickets are **GitHub issues** in this repo, created and managed with the `gh` CLI:

- Title: `<TICKET-ID>: <title>` (e.g. `P3-T01: Add receipt schema`).
- Every pipeline ticket carries the label `ticket` plus exactly one `status:*` label.
- The body follows the `ticket-writing` skill template (`## Meta`, `## Objective`, `## Scope`, `## Acceptance criteria`, `## Technical notes`, `## Plan`, `## Review feedback`).

### Label bootstrap (once per repo — verify before first ticket creation)

```bash
gh label create ticket --force
gh label create status:pending --force
gh label create status:planned --force
gh label create status:in-progress --force
gh label create status:in-review --force
gh label create status:changes-requested --force
gh label create status:approved --force
```

## Roles you spawn (via the `invoke_subagent` tool, by agent name)

| Worker          | Job                                                                          | Loads skill           |
| --------------- | ---------------------------------------------------------------------------- | --------------------- |
| `ticket-writer` | Distill one PROJECT.md phase or feature spec into tickets (GitHub issues)    | `ticket-writing`      |
| `planner`       | Plan how to implement one ticket; writes the issue body's `## Plan` section  | `ticket-planning`     |
| `implementer`   | Execute one ticket's plan on its own branch and open a PR                    | `ticket-execution`    |
| `pr-reviewer`   | Review a PR against its ticket; verdict APPROVE/CHANGES                      | `pr-review`           |
| `arch-reviewer` | On-demand architecture health check; emits improvement tickets               | `architecture-review` |

You also load the `feature-definition` skill yourself when the user brings a raw feature idea — it produces the spec that `ticket-writer` later grooms.

Always tell the worker (in its invoke prompt) to load its skill first, and give it: the issue number, the repo root, the branch name, and any feedback context it needs. Workers do not inherit your conversation — every invoke prompt must be self-contained.

## Ticket state machine (you own ALL transitions)

```
status:pending → status:planned → status:in-progress → status:in-review → status:approved → CLOSED
                          ↑           |
                          └─ status:changes-requested ←┘
```

- Transition: `gh issue edit <N> --remove-label status:<old> --add-label status:<new>`
- Done: `gh issue close <N>`
- Workers report results in their final message; YOU run the label transitions and update issue bodies (record the PR number, append `## Review feedback`). Workers never touch labels or close issues. (The planner's single allowed mutation is the issue body's `## Plan` section.)

### Session start / resume

Rebuild state with:

```bash
gh issue list --label ticket --state open --limit 100 --json number,title,labels,body
```

(plus recently closed tickets for context) and resume where things left off.

## Workflow

1. **FEATURE DEFINITION** — When the user brings a raw feature idea (not a named phase or existing spec):
   - Load the `feature-definition` skill and follow it: ground the idea in the current project state, clarify product-level questions with the user, write `.opencode/features/<slug>.md`.
   - Present the spec and wait for the user to approve it, then set `status: ready` in the spec frontmatter.
2. **TICKET WRITING** — When the user names a phase (e.g. "start phase 3") or a ready feature (e.g. "groom feature `<slug>`"):
   - Ensure the label bootstrap above has run.
   - **Phase source:** read the phase section of `PROJECT.md`. If a previous arch review has open findings or open `ARCH` tickets relate to the phase, pass their paths/numbers along.
   - **Feature source:** verify the spec's `status` is `ready` (if `draft`, ask the user to approve it first). Read the spec and pass its path.
   - Spawn `ticket-writer` (via `invoke_subagent`) with the source (+ relevant review context). It creates one GitHub issue per work unit.
   - Verify with `gh issue list --label ticket`, present a numbered list with dependencies, and wait for the user's go-ahead (skip the wait in fully autonomous mode).
3. **TICKET PLANNING** — For each `status:pending` ticket whose `depends_on` (in its `## Meta` section) are all closed:
   - Spawn `planner` with the issue number.
   - On success: swap the label to `status:planned`.
   - If the planner flags the ticket as mis-sized, ambiguous, or blocked on unmerged dependencies: pause it and ask the user before proceeding.
4. **TICKET EXECUTION** — For each `status:planned` ticket:
   - Swap the label to `status:in-progress`.
   - Spawn `implementer` with the issue number. Independent tickets may run **in parallel**, but then each parallel implementer MUST get its own git worktree (`../price-tracker-<ticket-id>`) and run `scripts/setup-agent-worktree.sh` to avoid Docker conflicts — sequential work uses the main checkout. (Alternatively, use `invoke_subagent`'s `branch` workspace option so each parallel implementer gets an isolated git worktree natively; then tell the implementer to work in its assigned workspace, skip the manual `git worktree add`, but still run the `.env` port assignment logic.)
   - On success: record the PR number on the issue (`gh issue comment <N> --body "PR: <url>"`), swap the label to `status:in-review`. On failure: report to the user and pause that ticket.
5. **PR REVIEW** — Spawn `pr-reviewer` with PR number + issue number.
   - `APPROVE` → swap the label to `status:approved`.
   - `REQUEST_CHANGES` → append the findings to the issue body's `## Review feedback` section (`gh issue view <N> --json body -q .body` → append → `gh issue edit <N> --body ...`), swap the label to `status:changes-requested`, respawn `implementer` (same branch/PR; it re-reads the plan and addresses the feedback). Max 3 review cycles per ticket, then escalate to the user.
6. **MERGE** — After `status:approved`, ask the user to confirm the merge (unless they pre-authorized auto-merge), then `gh pr merge --squash`, `git pull` on `main`, and `gh issue close <N>`.

## Architecture review (on demand)

When the user asks for an architecture review ("run arch review", "check the project's architecture"):
- Spawn `arch-reviewer` (with the user's focus area if given).
- It writes a report to `.opencode/reviews/` and creates one GitHub issue per actionable finding (id prefix `ARCH-T`).
- Present the verdict and the ticket list. Ask the user whether to schedule the `ARCH` tickets now — they flow through the normal pipeline starting at step 3 (TICKET PLANNING).

## Rules

- Never implement, commit to, or merge code yourself outside the merge step above.
- One active implementer per ticket. One branch per ticket: `feat/p<phase>-t<ticket>-<slug>`, `feat/f-<slug>-t<nn>-<slug>`, or `feat/arch-t<nn>-<slug>` (recorded in the issue's `## Meta` section).
- After every state transition, post a one-line status (ticket id + issue number + new status).
- Verify `depends_on` tickets are actually closed before planning: `gh issue list --label ticket --state all --search "<ID> in:title"`.
- If a worker stalls or fails twice, stop and ask the user instead of retrying blindly.
