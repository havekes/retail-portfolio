---
name: ticket-implementation
description: Orchestrate ticket implementation by planning code changes, modifying code across backend and frontend, running test suites, and creating pull requests.
---

# Ticket Implementation

Orchestrate the end-to-end execution of a groomed GitHub issue by integrating the `gh-issue-planner` and `gh-issue-executor` skills, verifying with tests, and opening a Pull Request.

## Inputs

- **Issue Number** (required): The GitHub issue number to implement.

## Workflow

### 1. Plan Resolution
- Check if `.opencode/plans/issue-<number>-plan.md` exists.
- If missing, run the `gh-issue-planner` skill to create the structured implementation plan.

### 2. Feature Branch Creation
Create and switch to a dedicated feature branch:
```bash
git checkout -b feat/issue-<number>-<short-description>
```

### 3. Task Execution (`gh-issue-executor`)
- Parse the plan into tracked tasks.
- Iterate through backend, frontend, database, and test changes.
- Update code using precise `replace_file_content` / `multi_replace_file_content` calls.
- Track progress by updating todo checkboxes in the plan file.

### 4. Verification & Testing
Execute automated test and lint suites:
- Backend check: `uv run ruff check && uv run ty check && uv run pytest`
- Frontend check: `npm run lint && npm run check && npm run test:run` (in `frontend/`)
Fix any failures before proceeding.

### 5. Git Commit & PR Creation
- Commit changes using standard conventional commit style:
  ```bash
  git add .
  git commit -m "feat(#<number>): <concise description>"
  ```
- Push branch and open Pull Request:
  ```bash
  git push origin feat/issue-<number>-<short-description>
  gh pr create --title "feat(#<number>): <title>" --body "Closes #<number>."
  ```

### 6. Output Summary
Provide:
- Issue number & PR link
- Changed files list
- Verification test results
