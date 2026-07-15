---
name: gh-issue-executor
description: Execute a GitHub issue implementation plan stored in `.opencode/plans/`. Use when the user wants to implement a planned issue (e.g., "implement issue X", "execute the plan for issue X", or "work on issue X").
---

# GitHub Issue Plan Executor

Take the plan produced by `/github-issue-planner` for a given GitHub issue and implement it.

## Inputs

- **Issue number** (required): The GitHub issue number. Derive it from the user's request.
- If not provided, ask: "Which GitHub issue number do you want to implement?"

## Plan file

The implementation plan must exist at:

```text
.opencode/plans/issue-<number>-plan.md
```

where `<number>` is just the digits (e.g. `68`, not `#68`).

If the file does not exist, tell the user to run the planner first:

```text
/github-issue-planner <number>
```

## Workflow

1. **Resolve the issue number and plan file**

   Announce which issue you are implementing and the plan file path:

   ```text
   Implementing GitHub issue #<number> from .opencode/plans/issue-<number>-plan.md
   ```

   Read the plan file. If it is missing or empty, stop and inform the user.

2. **Read supporting context**

   - Read any `AGENTS.md` files relevant to the touched areas.
   - If the plan references existing tests, read those tests to understand expected behavior.
   - Skim the files listed in **Files to Modify** so you understand the current state.

3. **Build a task list**

   Use **`todowrite`** to turn the plan into a tracked task list. Source tasks from:

   - The **Files to Modify** table.
   - The numbered backend / frontend changes in the plan.
   - The **Verification** checklist items.

   Do not implement before the todo list is created.

4. **Implement the changes**

   Iterate the tasks in a sensible order:

   - **Backend first**, then frontend, then tests, then verification.
   - Make minimal, idiomatic changes that match project conventions.
   - After each meaningful change, update the relevant todo items.
   - Keep the existing WebSocket / API event contracts unchanged unless the plan says otherwise.

   For each file change:

   - Read the file first.
   - Edit the file with the minimal diff that satisfies the plan.
   - Use the project's chosen test / lint commands as defined in `AGENTS.md` or `pyproject.toml` / `package.json`.

5. **Mark plan checkpoints**

   As you complete implementation work, update the plan file:

   - Check off items in the **Verification** section: `- [ ]` → `- [x]`.
   - Optionally add a "Progress" note to the **Notes** section describing what is done.

6. **Run verification**

   Execute the verification steps listed in the plan and any project-standard checks:

   - Backend lint / type checks (e.g., `uv run ruff check`, `uv run pyright` or `mypy`, `uv run pytest`).
   - Frontend lint / type checks (e.g., `npm run lint`, `npm run check`, `npm test`).
   - Manual checks described in the plan (e.g., start server, perform action, observe behavior).

   If a check fails, fix it. If the failure reveals a design or scope problem, pause and ask the user before redesigning.

7. **Summarize**

   When done (or paused), report:

   - Issue number and title (from the plan heading if available).
   - Which files were changed.
   - Verification results (checks passing / failing).
   - Anything left unaddressed or any follow-up needed.

## Constraints

- Do not implement if the plan file is missing. Plan first, implement second.
- Keep changes scoped to the plan. If you discover a larger issue, pause and report it.
- Follow project conventions from `AGENTS.md` and existing code patterns.
- Check off verification items in the plan as you complete them.
- Do not close the GitHub issue automatically; only report that the implementation is ready for review.

## Example invocation

```text
user: implement issue 68
```

Expected behavior:

1. Load `.opencode/plans/issue-68-plan.md`.
2. Create a todo list from the plan's files and verification items.
3. Implement the changes, updating todos and plan checkboxes as it goes.
4. Run backend and frontend checks.
5. Report completion.
