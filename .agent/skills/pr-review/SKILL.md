---
name: pr-review
description: Conduct end-to-end pull request reviews by executing existing quality-check (lint, types, tests) and code-review (bugs, standards, performance) skills, then submitting GitHub PR feedback.
---

# PR Review Workflow

Review Pull Requests comprehensively by uniting automated test/lint verification (via `quality-check` skill) and deep code analysis (via `code-review` skill).

## Inputs

- **PR Number or URL**: The GitHub Pull Request number to review.

## Workflow

### 1. Fetch Pull Request & Diff
Retrieve PR details and diff using the GitHub CLI:
```bash
gh pr view <number> --json title,body,author,headRefName,baseRefName,files
gh pr diff <number>
```

### 2. Execute `quality-check` Skill
Run full automated quality verification suites locally or on the checked-out PR branch:
- **Backend Quality**:
  - `uv run ruff check` (Linter)
  - `uv run ty check` (Type Checker)
  - `uv run pytest` (Backend Test Suite)
- **Frontend Quality**:
  - `npm run lint` (ESLint)
  - `npm run check` (Svelte/TypeScript check)
  - `npm run test:run` (Frontend Test Suite)

Document all passing and failing checks.

### 3. Execute `code-review` Skill
Perform line-by-line inspection of the diff against standard review areas:
- **Bugs & Edge Cases**: Swallowed exceptions, null checks, race conditions, boundary bugs.
- **Standards & Conventions**: Adherence to `AGENTS.md`, `openwiki/` documentation, consistent style.
- **Performance**: Complexity ($O(N^2)$), N+1 queries, unnecessary re-renders, resource leaks.
- **File Links**: Generate clickable file links (`file:///path/to/file#L10-L20`) for every comment.

### 4. Synthesize Review Verdict
Determine overall verdict:
- 🟢 **APPROVE**: All quality checks pass, no critical/major issues.
- 🟡 **COMMENT / APPROVE WITH NITS**: Passing checks, minor non-blocking suggestions.
- 🔴 **REQUEST CHANGES**: Failed quality checks, critical bugs, security flaws, or major standard violations.

### 5. Submit GitHub Review
Submit the review via GitHub CLI:
- Approved:
  ```bash
  gh pr review <number> --approve --body "<formatted_review_markdown>"
  ```
- Request Changes:
  ```bash
  gh pr review <number> --request-changes --body "<formatted_review_markdown>"
  ```
- Comment:
  ```bash
  gh pr review <number> --comment --body "<formatted_review_markdown>"
  ```

### 6. Output Summary
Report review completion, verdict, and link to PR.
