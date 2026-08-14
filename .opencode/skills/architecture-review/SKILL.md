---
name: architecture-review
description: Use when performing an on-demand architecture health check of the codebase — evaluating structure, boundaries, data model, and tech choices against the documented architecture (openwiki/, AGENTS.md), writing a report to .opencode/reviews/, and emitting actionable architectural improvement tickets as GitHub issues (id prefix ARCH-T) via the gh CLI.
---

# Architecture Review

Run when the user asks for an architecture review — decoupled from phases, repeatable any time. Goal: keep the project on rails by detecting architectural drift early and converting it into **executable tickets**, not just observations.

You assess the whole codebase (or the focus area the user named), not a single PR — line-level code quality is the pr-review step's job.

## Evaluation axes

1. **Documentation alignment** — does what exists match the architecture described in `openwiki/` and the `AGENTS.md` conventions (domain layering, schema/repository/service/API boundaries)? Any drift that upcoming features will pay for?
2. **Module boundaries** — are concerns separated (domain logic / persistence / API / UI)? Are dependencies one-directional, or is coupling creeping in?
3. **Data model fit** — does the schema support what upcoming features need (portfolio valuation, price history, broker sync)? Migrations manageable?
4. **Contracts** — are API shapes, internal interfaces, and JSON schemas stable and documented enough for upcoming tickets to build on?
5. **Cross-cutting concerns** — configuration, error handling strategy, logging, test strategy. Consistent or ad-hoc per ticket?
6. **Technical debt** — shortcuts taken under ticket scope pressure. Classify by interest rate: what compounds vs. what's inert?
7. **Prior reviews** — read earlier reports in `.opencode/reviews/` and open ARCH tickets (`gh issue list --label ticket --state open --search "ARCH-T in:title"`): were previous findings addressed or silently dropped? Never re-emit a finding that already has an open ticket.

## Method

- Read the documented intent (`openwiki/quickstart.md` + its architecture pages, and the `AGENTS.md` files), open ticket issues (`gh issue list --label ticket --state open`), and merged history since the last review (`git log`/`git show` on merge commits).
- Read the actual code structure — judge what exists, not what was planned.
- Every finding cites concrete files/modules. No vague "could be cleaner".

## Output 1 — report: `.opencode/reviews/<YYYY-MM-DD>-architecture.md`

```markdown
---
date: <YYYY-MM-DD>
verdict: sound | sound-with-concerns | needs-remediation
---

# Architecture Review <YYYY-MM-DD>

## Summary
<3–5 sentences: current state, overall verdict, the single most important observation.>

## Findings
### 1. <title> [severity: concern | risk | debt]
**Observation:** <what exists, with file/module references>
**Impact:** <what it costs if left alone>
**Recommendation:** <concrete action — ticketed as <TICKET-ID> (#<issue-number>), or "observation only" with why>

### 2. ...

## What went well
<Bullets — patterns worth keeping as conventions.>

## Prior finding disposition
<For each open finding/carry-over from previous reports and each open ARCH ticket: addressed / partially / still open / dropped (why). Omit if no prior review exists.>
```

## Output 2 — tickets as GitHub issues

Every **actionable** finding becomes a GitHub issue using the standard ticket body template (see the `ticket-writing` skill), created with:

```bash
gh issue create \
  --title "ARCH-T<NN>: <imperative title>" \
  --label ticket --label status:pending \
  --body "<issue body per the ticket-writing template>"
```

with:

- id `ARCH-T<NN>` (`NN` = zero-padded recommended execution order, blocking issues first)
- `## Meta` fields: `branch: feat/arch-t<nn>-<slug>`, `source:` pointing at the report file path
- scope small enough for one PR — split the finding if it isn't
- acceptance criteria that leave the codebase verifiably healthier, mechanically checkable
- `depends_on` between the arch tickets where order matters (e.g. a contract change before its consumers)

Findings that are pure observations (no action worth a PR) stay in the report only — say so in the finding's recommendation line.

## Rules

- A `needs-remediation` verdict requires at least one ticket whose technical notes mark it as blocking upcoming work.
- You write the report file and create the issues, then a summary as your final message: verdict, top findings, and the ticket list (id, issue number, title, depends_on).
- You never change implementation code and never touch status labels — tickets start as `status:pending`, the orchestrator owns state from there.
