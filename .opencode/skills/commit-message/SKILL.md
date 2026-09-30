---
name: commit-message
description: Generate a concise, high-quality git commit message following the 50/72 rule based on current diffs.
---

# Commit Message

Write a short, to-the-point commit message for the local changes.

## 1. Inspect

- `git status --short` — what changed (staged vs. unstaged vs. untracked).
- `git diff HEAD --stat`, then `git diff HEAD -- <file>` only for files whose intent isn't obvious from the stat. Use `--cached` instead of `HEAD` if only staged changes will be committed.

No changes → say there is nothing to commit.

## 2. Format (50/72)

- **Subject**: ≤50 chars, imperative (`Add`, not `Added`/`Adds`), capitalized, no trailing period.
- Blank line.
- **Body**: wrap at 72; explain *what* and *why*, not *how*. Omit for trivial changes.

## 3. Output

The message in a `text` code block, then a ready-to-run command:

```bash
git commit -m "Subject line" -m "Body wrapped at 72 chars."
```
