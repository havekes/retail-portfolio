---
name: code-review
description: Review code changes for bugs, code quality, adherence to code standards, and performance issues from a PR or local git diff.
---

# Code Review

Review code changes for bugs, code quality, code standards, and performance.

## 1. Fetch Changes

- **GitHub PR**: `gh pr view <number>` & `gh pr diff <number>`
- **Local Diff**:
  - Uncommitted: `git status && git diff`
  - Staged: `git diff --cached`
  - Branch vs main: `git diff main...HEAD`
  - Commit range: `git diff <commit_a>..<commit_b>`

If unspecified, check `git status` for local changes.

## 2. Focus Areas

- **Bugs & Correctness**: Edge cases, null checks, logic errors, off-by-one, swallowed errors, race conditions.
- **Code Quality**: Readability, simplicity, DRY principles, function scope, test coverage.
- **Code Standards**: Adherence to `AGENTS.md`, `openwiki/`, linters, typing, and repo patterns. Read full files around diffs using `view_file` for context.
- **Performance**: Algorithmic complexity ($O(N^2)$), N+1 queries, memory leaks, unnecessary re-renders/computations.

## 3. Output Format

Structure feedback concisely:

- **Summary**: Files changed & high-level assessment.
- **Critical Issues (🚨)**: Bugs, crashes, security vulnerabilities.
- **Major Issues (⚠️)**: Performance bottlenecks, quality/standards violations.
- **Nits & Minor Tweaks (💡)**: Naming, readability, doc cleanup.
- **Verdict**: 🟢 Approved | 🟡 Approved with Nits | 🔴 Needs Changes

*Always include clickable file links (`file:///path/to/file#L10-L20`) and actionable diff snippets for suggested fixes.*
