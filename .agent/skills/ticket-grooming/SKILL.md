---
name: ticket-grooming
description: Write, groom, triage, and structure GitHub issues with comprehensive acceptance criteria, technical context, and scope boundaries.
---

# Ticket Grooming & Creation

Groom existing GitHub issues or create detailed, actionable new GitHub issues from raw user feature requests or bug reports.

## Inputs

- **Requirement or Issue Number**: A user prompt describing a feature/bug, or an existing GitHub issue number (e.g. `#42` or `42`).

## Workflow

### 1. Requirements Discovery & Context Exploration
- Search the codebase using `grep_search` and inspect relevant source files using `view_file`.
- Check repository architectural documentation in `openwiki/` and `AGENTS.md`.
- List existing GitHub issues using `gh issue list` to prevent creating duplicate tickets.

### 2. Format Issue Specification
Draft the issue body following this structure:

```markdown
## Overview
<High-level summary of what needs to be accomplished>

## User Story
- **As a**: <role>
- **I want to**: <action>
- **So that**: <benefit>

## Technical Scope & Context
- **Affected Subsystems**: Backend (`src/`), Frontend (`frontend/`), Database (`migrations/`), etc.
- **Relevant Files & Symbols**: List key files and schemas.
- **In-Scope**: Explicit deliverables.
- **Out-of-Scope**: Non-goals and deferred items.

## Acceptance Criteria
- [ ] AC1: <Testable criterion>
- [ ] AC2: <Testable criterion>
- [ ] Verification: All test suites (`uv run pytest`, `npm run test:run`) and linter checks pass.

## Suggested Technical Approach
- Step-by-step guidance for the implementation subagent.
```

### 3. Create or Update GitHub Issue
- To create a new issue:
  ```bash
  gh issue create --title "<Descriptive Title>" --body-file <path_to_body_md> --label "<labels>"
  ```
- To update an existing issue:
  ```bash
  gh issue edit <number> --body-file <path_to_body_md>
  ```

### 4. Output Summary
Provide a summary containing:
- GitHub Issue ID and URL
- Issue Title
- Key Acceptance Criteria
- Assigned Labels
