---
name: ticket-writing
description: Use when shaping a rough feature idea or a feature spec from .opencode/features/ into small implementation tickets created as GitHub issues via the gh CLI. Covers clarifying requirements against the current codebase, ticket sizing rules, dependency analysis, ordering, the issue title/label conventions, and the issue body template.
---

# Ticket Writing

Distill one source of work — a rough feature idea **or** a feature spec from `.opencode/features/` (produced by the `feature-definition` skill, status `ready`) — into the smallest set of tickets that fully delivers its goal. Each ticket is a **GitHub issue** created with `gh issue create`.

You describe **what** each ticket must achieve. The **how** is decided later, per ticket, by the `ticket-planning` step — so keep `## Technical notes` to constraints and pointers, not implementation plans.

## Sources and naming

| | Idea source | Feature source |
| --- | --- | --- |
| Input | The user's rough idea text | Path to `.opencode/features/<slug>.md` |
| Ticket id prefix | `F-<slug>` | `F-<slug>` |
| `source:` meta field | `"idea: <one-line summary>"` | `".opencode/features/<slug>.md"` |

(One further ticket origin exists — `ARCH-T` tickets created directly by the `architecture-review` skill. You never groom those.)

Branch names follow the lowercase prefix pattern: `feat/f-<slug>-t<nn>-<slug>`.

For feature sources, groom from the spec's `## What needs to be done`, `## Scope`, and `## Definition of done` sections; treat its `## Open questions` defaults as decisions unless the user says otherwise. For idea sources, ground the idea in the actual codebase before writing anything (see procedure).

## Sizing rules

- **One ticket = one PR.** A single focused change a reviewer can evaluate in minutes.
- **Independently verifiable.** Each ticket has acceptance criteria that can be tested right after it merges, without waiting for later tickets.
- **Vertical slices over horizontal layers.** Prefer "schema + query layer for entity X" over "all schemas, then all queries" when the phase allows it.
- **~100–400 changed lines** is the sweet spot. If a ticket drafts bigger, split it. If two tickets are trivially small and tightly coupled, merge them.
- **Explicit seams.** A ticket that introduces an interface/boundary used by later tickets comes first and defines the contract in its acceptance criteria.

## Dependency analysis

- For every ticket, set `depends_on` (in `## Meta`) to the minimal list of ticket ids that must merge first.
- Tickets with disjoint `depends_on` closures are parallelizable — the orchestrator uses this, so be strict and accurate.
- Order tickets so the phase stays mergeable: each merge leaves `main` working (builds + tests pass).

## Carry-overs

If the orchestrator gave you a previous architecture review: its open findings/carry-over items are mandatory inputs. Either fold each into a ticket's scope/acceptance criteria or explicitly note in your report why it was deferred. (Newer reviews emit their findings directly as `ARCH` tickets — treat those as ordinary dependency inputs instead.)

## Procedure

1. Read the full source text (idea or feature spec) and its goal.
2. Ground it in the current codebase: read the domains, routes, components, and tests it touches. If requirements stay ambiguous after reading the code, STOP and return your clarifying questions in your final message instead of guessing — the orchestrator relays the answers back to you.
3. Read the carry-over/findings section of the previous arch review (if provided).
4. List candidate work units; apply the sizing rules; determine dependencies.
5. Create one GitHub issue per ticket, in execution order (`NN` = zero-padded execution order):

   ```bash
   gh issue create \
     --title "<PREFIX>-T<NN>: <imperative title, <= 60 chars>" \
     --label ticket --label status:pending \
     --body "<issue body per the template below>"
   ```

   If the labels don't exist yet, create them first: `gh label create ticket --force` and `gh label create status:pending --force`.
6. Final message: numbered ticket list (id, issue number + URL, title, depends_on) + one sizing rationale line each.

## Issue body template

```markdown
## Meta
- id: <PREFIX>-T<NN>
- depends_on: []            # ticket ids that must be closed first
- branch: feat/<prefix-lowercase>-t<nn>-<short-slug>
- source: "idea: <one-line summary>"   # or ".opencode/features/<slug>.md" or ".opencode/reviews/<date>-architecture.md"

## Objective

<1–3 sentences: what this delivers and why it matters to the phase/feature goal.>

## Scope

**In scope:**
- <concrete deliverable>

**Out of scope:**
- <explicit exclusion, especially tempting adjacent work>

## Acceptance criteria

- [ ] <testable statement — a reviewer can verify each one mechanically>
- [ ] Build passes and relevant tests pass

## Technical notes

<Relevant constraints, file/module pointers, contracts to honor, carry-over items from arch review. Leave empty if none.>

## Plan

<Empty at creation. The ticket-planning step fills this in via gh issue edit: approach, files to touch, ordered steps, verification.>

## Review feedback

<Empty at creation. Orchestrator appends PR-review findings here.>
```

State is tracked by the single `status:*` label (owned by the orchestrator) — the body has no status field.

## File output

Tickets live only as GitHub issues — you create no persistent local files. Temp files (issue-body payloads for `gh issue create --body-file`, working notes) go to `.opencode/scratch/` — never the repo root or `/tmp`.

## Quality bar for your output

- A stranger could implement each ticket without reading the source text.
- No ticket requires "and then also" — that is two tickets.
- Acceptance criteria are observable behavior, not aspirations ("endpoint returns X for Y", not "works well").
