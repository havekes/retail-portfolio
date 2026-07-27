---
name: ticket-planning
description: Use when planning how to implement a specific ticket (a GitHub issue labeled "ticket") — analyzing the affected code, choosing the approach, and writing a concrete step-by-step implementation plan into the issue body's ## Plan section via gh issue edit. Planning always precedes execution; the executor follows the plan.
---

# Ticket Planning

Turn one ticket (the **what**) into a concrete implementation plan (the **how**) that the executor can follow without re-deriving the approach. You plan — you never write implementation code.

## Inputs

- The ticket's GitHub issue number — read it fully with `gh issue view <N> --comments`: objective, scope, acceptance criteria, technical notes, any review feedback.
- The repo root.

## Ground the plan in reality

- Read the actual code the ticket will touch: neighboring modules, existing patterns, related tests. Cite real files and symbols in the plan — no guessed paths.
- Verify every `depends_on` ticket (listed in `## Meta`) is actually reflected in the merged codebase (the work your plan builds on exists). Cross-check: `gh issue list --label ticket --state all --search "<ID> in:title"` — dependencies must be closed.
- Choose ONE approach. If two are viable, pick the one matching existing project conventions and record the rejected alternative in one line (why not).

## Write the plan

Fetch the current body (`gh issue view <N> --json body -q .body`), replace the empty `## Plan` section with the content below, and write it back with `gh issue edit <N> --body "<updated body>"` (or `--body-file`):

```markdown
## Plan

**Approach:** <1–3 sentences: the strategy and why it fits this codebase.>

**Files:**
- `<path>` — <create|modify>: <what changes there>

**Steps:**
1. <ordered, atomic step — each independently checkable>
2. ...

**Verification:**
- <exact commands to run (build/test/lint) and what to observe per acceptance criterion>

**Risks / watch-outs:**
- <edge cases, migration hazards, ordering constraints. Omit section if none.>
```

## Rules

- The plan must cover **every** acceptance criterion — each criterion maps to at least one step and one verification.
- Stay inside the ticket's scope. If planning reveals the ticket is mis-sized or its scope is wrong, do NOT expand the plan to compensate — flag it in your final message so the orchestrator can escalate.
- No real code in the plan beyond short signatures or sketches; the executor writes the code.
- Your **only** mutation is that one issue-body edit — no other sections (preserve them byte-for-byte), no other issues, no files, no labels (status belongs to the orchestrator), no git operations.

## Final message

Report: the chosen approach (2–3 sentences), the file list (create/modify), any risks or red flags (mis-sized ticket, missing dependency, ambiguous acceptance criteria), and explicit confirmation that the plan covers every acceptance criterion.
