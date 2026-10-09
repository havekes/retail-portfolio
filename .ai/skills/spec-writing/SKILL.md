---
name: spec-writing
description: Use when turning a rough idea, a ready feature spec (.ai/features/), or an architecture review report (.ai/reviews/) into small, dependency-ordered tickets created as GitHub issues with the implementation plan already written — or when (re)planning an existing ticket issue whose ## Plan is empty or stale. Covers clarifying questions, sizing, dependencies, the issue template, and the plan format.
---

# Spec Writing

Turn one source of work into the smallest set of tickets that fully delivers it. Each ticket is a **GitHub issue** holding both the **what** (objective, scope, acceptance criteria) and the **how** (`## Plan`). Explore the codebase once and reuse that knowledge across every ticket — that is the point of doing both in one pass.

You never write implementation code, never run git mutations, never change `status:*` labels on existing issues.

## Modes

| Mode | Input | Output |
| --- | --- | --- |
| `create` (idea) | Rough idea text | New issues, id prefix `F-<slug>`, `source: "idea: <one-line summary>"` |
| `create` (feature) | `.ai/features/<slug>.md` (`status: ready` — refuse `draft`) | New issues, id prefix `F-<slug>`, `source: ".ai/features/<slug>.md"` |
| `create` (arch) | `.ai/reviews/<date>-architecture.md` | New issues, id prefix `ARCH`, `source:` the report path, one per actionable finding |
| `plan` | Existing issue number(s) `#N` | `## Plan` section written/replaced in each issue body; nothing else changes |

Every ticket's `base:` is the feature branch the orchestrator gave you (`feat/<slug>`).

Feature source: groom from `## What needs to be done`, `## Scope`, `## Definition of done`; treat `## Open questions` defaults as decisions. Arch source: only findings whose recommendation is actionable; skip findings that already have an open `ARCH-T` issue (same command, `OPEN` rows).

**Ids never repeat.** Before numbering, list existing ids for the prefix across all states: `gh issue list --label ticket --state all --limit 500 --json title,state -q '.[] | select(.title | startswith("<PREFIX>-T")) | "\(.state) \(.title)"'`, and continue after the highest `NN` (a slug reused from closed tickets continues its numbering).

Legacy paths: `.agent/<dir>/…` and `.opencode/<dir>/…` in old issues now live at `.ai/<dir>/…`.

## Procedure

1. Read the source fully (`plan` mode: `gh issue view <N> --comments`, including `## Review feedback`).
2. Ground it in the code: read the modules, routes, components, and tests it touches. Read only what the tickets need — targeted `rg`/`find`, then the relevant ranges.
3. **Ambiguity gate** — if a product-level requirement is still unclear after reading the code, STOP: return numbered clarifying questions (each with the default you'd use) as your final message and create nothing. Implementation choices are yours to make — don't ask about those.
4. `create`: list work units, apply the sizing rules, set dependencies.
5. Write each plan (format below), grounded in real files and symbols you read.
6. `create`: create issues in execution order (`NN` = zero-padded order). `plan`: fetch the body, replace only `## Plan` (every other section byte-for-byte), write it back.
7. Final message (see end).

## Sizing rules

- **One ticket = one PR**, reviewable in minutes; ~100–400 changed lines. Bigger → split. Two trivial, tightly coupled tickets → merge.
- **Independently verifiable** right after it merges; each merge leaves the feature branch green.
- **Vertical slices** over horizontal layers.
- **Explicit seams**: a ticket introducing an interface used later comes first and states the contract in its acceptance criteria.
- No ticket needs "and then also" — that's two tickets.

## Dependencies

- `depends_on` = minimal list of ticket ids that must merge first. Be strict: disjoint closures run in parallel.
- Downstream tickets are planned **before** upstream ones merge. Plan against the contract stated in the upstream ticket's acceptance criteria and plan — name the upstream symbols/endpoints you rely on so drift is detectable later.

## Plan format

```markdown
## Plan

**Approach:** <1–3 sentences; why it fits this codebase. One rejected alternative + why, if any was viable.>

**Files:**
- `<path>` — create|modify: <what changes>

**Steps:**
1. <ordered, atomic, independently checkable>

**Verification:**
- `./scripts/agent-test <test path>` — <what it proves>
- <per acceptance criterion: command/test and expected observation>

**Risks:** <edge cases, migration hazards, ordering. Omit if none.>
```

Rules: every acceptance criterion maps to ≥1 step and ≥1 verification; no real code beyond short signatures; stay inside scope — if the ticket is mis-sized or wrong, flag it instead of stretching the plan. All test/lint commands go through `./scripts/agent-test` (it runs inside Docker) — never raw `pytest`/`npm`.

## Issue template

Create with `gh issue create --title "<ID>: <imperative title, ≤60 chars>" --label ticket --label status:planned --body-file .ai/scratch/<id>-body.md`. If labels are missing: `gh label create <name> --force`.

```markdown
## Meta
- id: <PREFIX>-T<NN>
- depends_on: []
- base: feat/<slug>                  # feature integration branch the PR targets
- branch: feat/<prefix-lowercase>-t<nn>-<short-slug>
- source: <see Modes table>

## Objective
<1–3 sentences: what this delivers and why.>

## Scope
**In scope:**
- <concrete deliverable>

**Out of scope:**
- <tempting adjacent work>

## Acceptance criteria
- [ ] <observable, mechanically verifiable — "endpoint returns X for Y", not "works well">
- [ ] `./scripts/agent-test` passes

## Technical notes
<Constraints, contracts, pointers. Omit content if none.>

## Plan
<per Plan format>

## Review feedback
```

State lives only in the `status:*` label — no status field in the body.

## Files

No persistent local files — issues are the output. Issue-body payloads and notes go to `.ai/scratch/` (never repo root or `/tmp`); optional local plan drafts to `.ai/notes/<id>-plan.md`.

## Final message

- `create`: numbered list — id, issue number + URL, title, depends_on, one line on sizing. For arch sources, also each skipped finding and why.
- `plan`: per issue — approach (2–3 sentences), files, risks.
- Always: red flags (mis-sized, ambiguous criteria, contract conflicts with other open tickets) and confirmation every acceptance criterion is covered.

Quality bar: a stranger can implement each ticket from the issue alone.
