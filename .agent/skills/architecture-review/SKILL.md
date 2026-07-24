---
name: architecture-review
description: Review a proposed implementation plan or existing architecture for a given task, ensuring alignment with project patterns, scalability, and maintainability.
---

# Architecture Review

Review the technical design and architecture for a proposed feature, change, or plan.

## Inputs
- **Plan or Design Doc**: Path to the implementation plan (e.g., `.opencode/plans/issue-<number>-plan.md`) or architectural description.

## Workflow

1. **Understand the Context**:
   - Read the proposed plan or design document.
   - Explore the relevant sections of the codebase (e.g., existing models, services, routers, frontend state).
   - Read any relevant `AGENTS.md` and OpenWiki documentation to understand repository conventions.

2. **Evaluate the Design**:
   Focus on the following architectural aspects:
   - **System Design & Flow**: Does the proposed data flow make sense? Are the right components (backend vs frontend) handling the logic?
   - **Consistency**: Does the approach follow existing repo conventions and patterns?
   - **Scalability & Performance**: Will this approach scale? Are there potential N+1 queries, heavy computations on the main thread, or unoptimized data fetching?
   - **Security**: Are there potential security risks, missing authorization checks, or exposed sensitive data?
   - **Maintainability**: Is the design modular? Is it overly complex or over-engineered for the problem?

3. **Output Format**:
   Produce a clear, actionable Architecture Review report:
   - **Summary**: High-level assessment of the design.
   - **Strengths**: What works well in the proposed plan.
   - **Architectural Risks (🚨)**: Critical flaws, security risks, or major deviations from repo conventions.
   - **Recommendations (💡)**: Actionable suggestions to improve the design, simplify the approach, or enhance performance.
   - **Verdict**: 🟢 Approved | 🟡 Approved with Changes | 🔴 Needs Redesign

If any Architectural Risks are identified, provide clear alternatives or suggest a redesign before implementation begins.
