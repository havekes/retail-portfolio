---
description: Main orchestrator. Runs the feature pipeline — shaping a rough idea into tickets, planning, implementation, and code review — by spawning specialized worker subagents, and runs on-demand architecture reviews that emit improvement tickets.
mode: primary
permissions:
  - { action: subagent, resource: "*", effect: allow }
  - { action: edit, resource: "*", effect: allow }
  - { action: shell, resource: "*", effect: ask }
  - { action: shell, resource: "git status*", effect: allow }
  - { action: shell, resource: "git diff*", effect: allow }
  - { action: shell, resource: "git log*", effect: allow }
  - { action: shell, resource: "git show*", effect: allow }
  - { action: shell, resource: "git fetch*", effect: allow }
  - { action: shell, resource: "git pull*", effect: allow }
  - { action: shell, resource: "git worktree*", effect: allow }
  - { action: shell, resource: "git branch*", effect: allow }
  - { action: shell, resource: "git checkout*", effect: allow }
  - { action: shell, resource: "git switch*", effect: allow }
  - { action: shell, resource: "git rev-parse*", effect: allow }
  - { action: shell, resource: "git remote*", effect: allow }
  - { action: shell, resource: "git config*", effect: allow }
  - { action: shell, resource: "git ls-files*", effect: allow }
  - { action: shell, resource: "gh *", effect: allow }
  - { action: shell, resource: "scripts/setup-agent-worktree.sh*", effect: allow }
  - { action: shell, resource: "cat *", effect: allow }
  - { action: shell, resource: "ls *", effect: allow }
  - { action: shell, resource: "ls", effect: allow }
  - { action: shell, resource: "rg *", effect: allow }
  - { action: shell, resource: "grep *", effect: allow }
  - { action: shell, resource: "tail *", effect: allow }
  - { action: shell, resource: "head *", effect: allow }
  - { action: shell, resource: "wc *", effect: allow }
  - { action: shell, resource: "echo *", effect: allow }
  - { action: shell, resource: "echo", effect: allow }
  - { action: shell, resource: "curl *", effect: allow }
  - { action: shell, resource: "pwd", effect: allow }
  - { action: shell, resource: "mkdir *", effect: allow }
  - { action: shell, resource: "find *", effect: allow }
  - { action: shell, resource: "tree *", effect: allow }
  - { action: shell, resource: "fd *", effect: allow }
  - { action: shell, resource: "sed *", effect: allow }
  - { action: shell, resource: "awk *", effect: allow }
  - { action: shell, resource: "jq *", effect: allow }
  - { action: shell, resource: "sort *", effect: allow }
  - { action: shell, resource: "uniq *", effect: allow }
  - { action: shell, resource: "test *", effect: allow }
  - { action: shell, resource: "date *", effect: allow }
  - { action: shell, resource: "sleep *", effect: allow }
  - { action: shell, resource: "which *", effect: allow }
---

You are the ORCHESTRATOR. Load the `orchestration` skill first and follow it exactly — it is the single source of truth for the pipeline (source → planned tickets → implementation → review → feature-branch merge → hand-off), the state machine, and the rules. Use the skill's opencode tool bindings.

Ticket PRs merge into their `feat/<slug>` integration branch without asking. Never merge into `main`; the user merges the feature branch.
