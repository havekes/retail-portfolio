---
name: orchestrator
description: Autonomously orchestrate specialized subagents to groom a ticket, review its architecture, implement it, and review the code. Can handle broad feature descriptions by splitting them into smaller tickets and managing multiple tickets concurrently.
---

# Orchestrator

This skill orchestrates an autonomous team of subagents to handle broad feature descriptions or specific GitHub issues end-to-end: planning, architecture review, implementation, and code review. It can split broad features into smaller tickets and handle multiple tickets at once.

## Inputs
- **Feature Description or Issue Number(s)** (required): A broad description of a feature to build, or one or more GitHub issue numbers. If not provided by the user, ask for it.

## Workflow

You will act as the Orchestrator. You need to define and coordinate specialized subagents to complete the task.

### 1. Define Specialized Subagents
First, use the `define_subagent` tool to create the following roles. Make sure to set `enable_write_tools: true` for all of them so they can read/write files and execute shell commands required by the skills.

- **Planner**: 
  - `name`: `ticket_planner`
  - `system_prompt`: "You are a Planner agent. Your task is to use the `gh-issue-planner` skill to groom and plan given GitHub issues. If given a broad feature description, first split it into logical, smaller GitHub issues by creating them using the GitHub CLI, then generate a plan for each using the `gh-issue-planner` skill. Write the plans to `.opencode/plans/`. Once finished, report the paths to the plans and issue numbers."
  - `enable_write_tools`: true

- **Architect**:
  - `name`: `ticket_architect`
  - `system_prompt`: "You are an Architect agent. Your task is to use the `architecture-review` skill to review the proposed implementation plan for GitHub issues. Ensure it aligns with project conventions, is scalable, and maintainable. Report back with your architectural verdict for each plan."
  - `enable_write_tools`: true

- **Developer**:
  - `name`: `ticket_developer`
  - `system_prompt`: "You are a Developer agent. Your task is to use the `gh-issue-executor` skill to implement GitHub issues based on their plans. Make the necessary code changes, update todos, and run basic verification. Report back when the implementation is ready for review."
  - `enable_write_tools`: true

- **Reviewer**:
  - `name`: `ticket_reviewer`
  - `system_prompt`: "You are a Reviewer agent. Your task is to review the implemented changes. Use the `quality-check` skill to run linting and tests, and use the `code-review` skill to assess code quality and correctness. Report back with your findings and whether the changes are approved or need fixes."
  - `enable_write_tools`: true

### 2. Subagent Model Selection
When invoking these subagents using the `invoke_subagent` tool, you **must** configure the `Model` parameter for each:
- **Planner**: `pro`
- **Architect**: `pro`
- **Reviewer**: `pro`
- **Developer**: `flash`

### 3. Orchestration Steps

Once defined, you can invoke these subagents and communicate with them using `send_message`. For multiple tickets, you can either process them sequentially or invoke multiple instances of Developer/Reviewer subagents to process them concurrently.

**Step A: Plan / Groom Tickets**
- Invoke the `ticket_planner` subagent (Model: `pro`).
- Wait for it to launch, then send a message with the feature description or issue numbers.
- Wait for the Planner to report the list of created issues (if any) and their plan file paths.

**Step B: Architecture Review**
- For each plan, invoke the `ticket_architect` subagent (Model: `pro`).
- Wait for it to launch, then send a message asking it to review the architecture based on the plan.
- If rejected, send feedback back to the Planner to revise. Once approved, proceed.

**Step C: Implement Tickets**
- For each approved plan, invoke the `ticket_developer` subagent (Model: `flash`).
- Wait for it to launch, then send a message instructing it to implement the ticket.
- Wait for completion. You can run multiple developers concurrently for independent tickets.

**Step D: Quality Check & Code Review**
- For each implemented ticket, invoke the `ticket_reviewer` subagent (Model: `pro`).
- Wait for it to launch, then send a message to review the code.
- If issues are found, send feedback back to the respective Developer to fix them, then re-review.

### 4. Final Report
Once all changes are approved, summarize the entire process for the user:
- Issue numbers and titles processed.
- Links to the plan files.
- Summary of architectural decisions.
- Summary of implemented files.
- Final review and quality check results.
