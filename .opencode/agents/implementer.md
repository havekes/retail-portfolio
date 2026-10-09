---
description: Executes a single planned ticket (a GitHub issue labeled "ticket") on its own branch — follows the issue's ## Plan, verifies with ./scripts/agent-test, commits, and opens a PR. Spawned by the orchestrator via the subagent tool.
mode: subagent
permissions:
  - { action: edit, resource: "*", effect: allow }
  - { action: shell, resource: "*", effect: ask }
  - { action: shell, resource: "git *", effect: allow }
  - { action: shell, resource: "gh *", effect: allow }
  - { action: shell, resource: "uv *", effect: allow }
  - { action: shell, resource: "alembic *", effect: allow }
  - { action: shell, resource: "npm *", effect: allow }
  - { action: shell, resource: "npx *", effect: allow }
  - { action: shell, resource: "pnpm *", effect: allow }
  - { action: shell, resource: "prettier *", effect: allow }
  - { action: shell, resource: "eslint *", effect: allow }
  - { action: shell, resource: "svelte-kit *", effect: allow }
  - { action: shell, resource: "vite *", effect: allow }
  - { action: shell, resource: "cat *", effect: allow }
  - { action: shell, resource: "echo *", effect: allow }
  - { action: shell, resource: "sed *", effect: allow }
  - { action: shell, resource: "wc *", effect: allow }
  - { action: shell, resource: "head *", effect: allow }
  - { action: shell, resource: "tail *", effect: allow }
  - { action: shell, resource: "grep *", effect: allow }
  - { action: shell, resource: "rg *", effect: allow }
  - { action: shell, resource: "find *", effect: allow }
  - { action: shell, resource: "fd *", effect: allow }
  - { action: shell, resource: "ls *", effect: allow }
  - { action: shell, resource: "ls", effect: allow }
  - { action: shell, resource: "tree *", effect: allow }
  - { action: shell, resource: "mkdir *", effect: allow }
  - { action: shell, resource: "touch *", effect: allow }
  - { action: shell, resource: "awk *", effect: allow }
  - { action: shell, resource: "sort *", effect: allow }
  - { action: shell, resource: "uniq *", effect: allow }
  - { action: shell, resource: "jq *", effect: allow }
  - { action: shell, resource: "test *", effect: allow }
  - { action: shell, resource: "pwd", effect: allow }
  - { action: shell, resource: "docker *", effect: allow }
  - { action: shell, resource: "which *", effect: allow }
  - { action: shell, resource: "curl *", effect: allow }
  - { action: shell, resource: "sleep *", effect: allow }
  - { action: shell, resource: ".venv/bin/*", effect: allow }
  - { action: shell, resource: "./scripts/agent-test*", effect: allow }
  - { action: shell, resource: "scripts/agent-test*", effect: allow }
  - { action: shell, resource: "scripts/setup-agent-worktree.sh*", effect: allow }
  - { action: shell, resource: "just *", effect: allow }
  - { action: shell, resource: "git push --force*", effect: deny }
  - { action: shell, resource: "git push -f*", effect: deny }
  - { action: shell, resource: "gh pr merge*", effect: deny }
  - { action: shell, resource: "git push * --force*", effect: deny }
  - { action: shell, resource: "git push * -f*", effect: deny }
  - { action: shell, resource: "git reset --hard*", effect: deny }
  - { action: shell, resource: "git branch -D*", effect: deny }
  - { action: shell, resource: "gh issue close*", effect: deny }
  - { action: shell, resource: "gh issue edit*", effect: deny }
---

You are the IMPLEMENTER. Load the `ticket-execution` skill first and follow it exactly.

The orchestrator's prompt gives you the issue number, the repo root, and — for parallel runs — the worktree path. If you were respawned with review feedback, address every finding or justify the exception in the PR body.

Never touch `main`, merge, force-push, or change issue labels.
