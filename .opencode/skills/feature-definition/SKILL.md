---
name: feature-definition
description: Use when turning a raw, unstructured feature idea into a clean product-level feature description grounded in the current state of the project. Produces a spec in .opencode/features/ — input for ticket-writing, not a ticket itself.
---

# Feature Definition

Take a raw idea ("wouldn't it be cool if...", a one-liner, a pain point) and shape it into a precise, product-level feature description that the ticket-writer can later groom into implementation tickets. You describe **what and why**, not **how to build it** — no tickets, no task breakdowns, no implementation plans.

## Inputs

- The raw idea in the user's own words.
- Optionally: constraints, prior art, or related feature specs in `.opencode/features/`.

## Grounding in current state

Before writing anything, look at what exists — the spec must be honest about the gap between idea and reality:

1. Read `README.md` and `openwiki/quickstart.md` — where this idea fits (or deliberately deviates from) the current project.
2. Scan the relevant code structure — does a foundation for this already exist? What does the current UX/data model look like in the affected area?
3. Scan open ticket issues (`gh issue list --label ticket --state open`) and `.opencode/reviews/` — in-flight or completed work that overlaps; arch-review findings that constrain the feature.

Cite concrete files/modules when describing the current state. If the idea conflicts with something already built or planned, surface the conflict — don't paper over it.

## Clarify before writing

If the idea is ambiguous on a product-level decision (target user, scope boundary, behavior choice), ask the user — pick the smallest set of decisions that change what the spec says. Do not ask about implementation details; those belong to grooming. If a reasonable default exists, state it as an assumption in the spec instead of asking.

## Output — write to `.opencode/features/<short-slug>.md`

```markdown
---
title: <feature name>
slug: <short-slug>
status: draft
date: <YYYY-MM-DD>
---

# <Feature name>

## Problem

<The pain or opportunity, from the user's perspective. Why now?>

## Goal

<1–3 sentences: the end state when this feature exists. Observable, not aspirational.>

## User-facing behavior

<What a user sees/does, step by step or as concrete scenarios. Include empty/error states if they shape scope.>

## Scope

**In scope:**
- <product-level capability>

**Out of scope:**
- <explicit exclusion — especially tempting adjacent ideas from the raw input>

## Current state & gap

<What exists today in the codebase/blueprint relevant to this feature, with file/module references, and what's missing.>

## What needs to be done

<High-level work areas (e.g. "persist X", "API endpoint for Y", "UI surface for Z") — product/technical capabilities, NOT tickets. Sequencing hints only where one area hard-blocks another.>

## Open questions

<Unresolved product decisions, each with the default you'll proceed with if unanswered. Remove this section once empty.>

## Definition of done

- [ ] <verifiable product-level statement — "user can do X and see Y">
```

## Status lifecycle

- `draft` — written, awaiting user sign-off.
- `ready` — user approved; eligible input for ticket-writing.
- Flip `status: ready` only on explicit user approval.

## Quality bar

- A reader who never heard the raw idea understands what is being built and why, without asking you anything.
- Every "Current state & gap" claim traces to a real file, ticket/issue, or review.
- The spec contains zero ticket IDs, branch names, or file-level implementation plans — those belong to ticket writing and planning.
- Sizing is honest: if the idea is clearly multiple features, say so and spec only the first slice.
