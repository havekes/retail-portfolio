---
name: commit-message
description: Generate a concise, high-quality git commit message following the 50/72 rule based on current diffs.
---

# Commit Message

Generate a clear, short, and to-the-point Git commit message by inspecting local changes (staged and unstaged diffs).

## 1. Inspect the Diffs

Run git commands to inspect repository changes:
- `git status` to view untracked, modified, and staged files.
- `git diff --cached` to view staged changes.
- `git diff` to view unstaged changes.
- `git diff HEAD` to view all combined changes.

If there are no changes, inform the user that there is nothing to commit.

## 2. Commit Message Structure (50/72 Rule)

Follow Git commit message standards:

### Subject Line (Max 50 Characters)
- **Length**: Strict maximum of 50 characters.
- **Mood**: Use imperative mood (e.g., `Add feature` instead of `Added feature` or `Adds feature`).
- **Capitalization**: Capitalize the first word.
- **Punctuation**: Do not end with a period.
- **Clarity**: Short and to the point summary of the core change.

### Blank Line
- Include a blank line between the subject line and the body.

### Body (Wrapped at 72 Characters)
- **Line Length**: Wrap lines strictly at 72 characters.
- **Content**: Explain *what* changed and *why* (the motive/reasoning), not *how* (the code diff shows how).
- **Tone**: Keep it concise and to the point.
- **Omission**: Skip the body if the subject line fully explains a trivial change (e.g., minor typo fix).

## 3. Output Format

Present the commit message formatted clearly in a code block and provide a ready-to-run git commit command:

```text
Subject line under 50 characters

Optional body wrapped at 72 characters explaining what and why.
Can be multiple paragraphs or bullet points if needed.
```

Suggested command:
```bash
git commit -m "Subject line" -m "Body line 1
Body line 2"
```
