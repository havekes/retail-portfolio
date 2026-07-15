---
name: gh-issue-planner
description: Plan a GitHub issue implementation and write it to `.opencode/plans/`. Use when the user wants you to fetch an issue from GitHub and produce a focused implementation plan.
---

# GitHub Issue Planner

Create an implementation plan for a GitHub issue and write it to `.opencode/plans/`.

## Inputs

- **Issue number** (required): The GitHub issue number. Derive it from the user's request.
- If not provided, ask: "Which GitHub issue number do you want to plan?"

## Output

A Markdown file written to:

```text
.opencode/plans/issue-<number>-plan.md
```

## Workflow

1. **Fetch the issue**
   Use the GitHub CLI to retrieve the issue title and body:

   ```bash
   gh issue view <number> --json title,body,labels,state,comments,assignees,author,createdAt,url
   gh issue view <number> --comments
   ```

2. **Explore the codebase**
   Identify the components the issue talks about. Search for relevant terms, read the files that will likely need to change, and understand the current behavior. Look at:

   - Frontend state/components related to the issue
   - Backend routers, services, tasks, and models
   - Existing tests and patterns
   - `AGENTS.md` files for project conventions

   Keep reading and searching until you can explain:

   - What currently happens
   - Why the issue occurs
   - Which files are involved
   - What a minimal, idiomatic fix looks like

3. **Draft the plan**
   The Markdown file should include these sections:

   - **Problem Statement**: What the user reported / what is broken.
   - **Root Cause**: Why it happens (architecture/state flow).
   - **Current Flow**: Step-by-step description of how the relevant feature works today.
   - **Proposed Solution**: High-level approach, with reasoning.
   - **Backend Changes**: Specific files and functions for backend work.
   - **Frontend Changes**: Specific files and components for frontend work.
   - **Verification**: Manual and/or automated checks to confirm the fix.
   - **Out of Scope**: What is intentionally not being addressed.
   - **Files to Modify**: A table mapping area, file path, and change.
   - **Notes**: Any gotchas, conventions, or follow-up items.

   Use concrete file paths, function names, and, where helpful, short code snippets or key names. Keep the plan focused on the requested issue.

4. **Write the file**
   Create the directory if needed:

   ```bash
   mkdir -p .opencode/plans
   ```

   Then write the plan to `.opencode/plans/issue-<number>-plan.md`.

5. **Report back**
   Summarize what was written:

   - Issue title and number
   - One-line problem statement
   - Plan file path
   - Brief list of the main changes proposed

## Constraints

- Do not implement the plan while doing the planning. The output is a Markdown plan, not code changes.
- Use minimal, idiomatic changes that follow the project's existing patterns and `AGENTS.md` guidance.
- If a requirement is ambiguous after reading the issue and the code, note the ambiguity in the plan and propose a reasonable default.
- Always follow the project's language conventions (e.g., English) in the plan.
