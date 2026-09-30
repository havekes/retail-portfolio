---
name: architecture-review
description: Use when performing an on-demand architecture health check of the codebase — evaluating structure, boundaries, data model, and tech choices against the documented architecture (openwiki/, AGENTS.md) and writing a findings report to .ai/reviews/. Tickets are created afterwards from the report by the spec-writing skill.
---

# Architecture Review

On demand, any time. Detect architectural drift early and express it as **actionable findings** that `spec-writing` can turn into `ARCH-T` tickets. Whole codebase (or the user's focus area), not a single PR — line-level quality is `pr-review`'s job.

You write the report only. You never change code and never create or edit issues.

## Method

1. Documented intent: `openwiki/quickstart.md` + its architecture pages, the `AGENTS.md` files.
2. History: the latest report in `.ai/reviews/`, open `ARCH-T` issues (`gh issue list --label ticket --state open --limit 200 --json number,title -q '.[] | select(.title | startswith("ARCH-T"))'`), merges since that report (`git log --merges --oneline --since=<date>`).
3. Actual structure: read what exists, not what was planned. Sample representative modules per layer rather than reading everything.
4. Every finding cites concrete files/modules. No vague "could be cleaner".

## Axes

1. **Documentation alignment** — code vs. `openwiki/` and `AGENTS.md` layering (schema/repository/service/API).
2. **Module boundaries** — separation of domain/persistence/API/UI; one-directional dependencies.
3. **Data model fit** — does the schema support upcoming work (see `.ai/features/`, open tickets)? Migrations manageable?
4. **Contracts** — API shapes and internal interfaces stable enough to build on.
5. **Cross-cutting** — config, errors, logging, tests: consistent or ad hoc?
6. **Tech debt** — by interest rate: what compounds vs. what's inert.
7. **Prior findings** — addressed, or silently dropped? Never re-raise a finding that has an open `ARCH-T` issue; reference it instead.

## Report: `.ai/reviews/<YYYY-MM-DD>-architecture[-<focus>].md`

```markdown
---
date: <YYYY-MM-DD>
verdict: sound | sound-with-concerns | needs-remediation
---

# Architecture Review <YYYY-MM-DD>

## Summary
<3–5 sentences: state, verdict, the single most important observation.>

## Findings
### 1. <title> [severity: concern | risk | debt] [actionable | observation] [blocking: yes|no]
**Observation:** <what exists, with file/module references>
**Impact:** <cost if left alone>
**Recommendation:** <concrete, PR-sized action with a verifiable outcome; or why it's observation-only>
**Order:** <depends on finding #X, if any>

## What went well
<Patterns worth keeping.>

## Prior finding disposition
<Each earlier finding / open ARCH-T issue: addressed / partial / open / dropped (why). Omit if no prior review.>
```

Rules: `needs-remediation` requires ≥1 actionable finding marked `blocking: yes`. Recommendations must be split to one-PR size so they map 1:1 to tickets.

## Final message

Verdict, report path, and the actionable findings (number, title, severity, blocking) — one line each on why it's worth a PR. Temp files → `.ai/scratch/`.
