---
title: Notes Revamp — Quick Scratch Pad with AI Summary
slug: notes-revamp
status: ready
date: 2026-09-21
---

# Notes Revamp — Quick Scratch Pad with AI Summary

## Problem

Notes are buried in the security page sidebar and take several clicks to add. The user wants them to feel like a scratch pad — jot down an idea, reminder, or key info in seconds — and wants an at-a-glance AI digest of what the accumulated (often rough/gibberish) notes actually say.

## Goal

Pressing (n) on the security page opens a content-first note dialog (scratch-pad feel). When notes exist, an AI summary appears at the top of the Notes group, weighting more recent notes more heavily, refreshed automatically as notes change.

## User-facing behavior

- On the security page, pressing `n` (when not typing in an input/textarea/contenteditable and no modal is open) opens the note creation dialog with focus in the content field. Escape/cancel is no-op.
- Note creation is content-only; the existing AI-generated title flow continues to fill the title.
- In the sidebar Notes group, when at least one note exists, an AI summary block renders at the top, above the note list.
- The summary refreshes automatically whenever the note set changes (create/update/delete) — shows a loading state while regenerating; on failure shows a compact error with retry.
- With zero notes, no summary block shows ("No notes yet" as today).

## Scope

**In scope:**
- Keyboard shortcut `n` on the security page to open note creation.
- Content-first creation dialog (no title field; focus on content).
- AI summary block at the top of the Notes group in the security sidebar.
- Recency weighting of notes in the summary, implemented at prompt level (timestamps passed to the model with instructions to weight recent notes more heavily).
- Summary generation dispatched to a huey background task (pattern precedent: `generate_note_title_task` in `src/market/task.py`), with the result persisted for the frontend to fetch.
- Auto-refresh of the summary on note create/update/delete (dispatch background regeneration; UI shows loading/error states and picks up the new summary when ready).

**Out of scope:**
- Global (non-security) notes or a notes page.
- Code-level recency tiers in the summary prompt, or streaming inline AI calls from the frontend/backend request path (generation goes through huey).
- Changing the securities notes data model, API contracts for CRUD, or note list rendering beyond adding the summary block.
- Markdown/rich text rendering of the summary.

## Current state & gap

- Notes are per-security: `SecurityNoteModel` (`src/market/model.py`, table `market_security_notes`) with title + content; CRUD routed via `src/market/router.py` (`/market/securities/{security_id}/notes`).
- Sidebar UI: `frontend/src/lib/components/actions-sidebar/note/note-group.svelte` with creation/view dialogs (`note-creation-dialog.svelte`, `note-view-dialog.svelte`); API client `frontend/src/lib/api/notesService.ts`.
- An AI summarize endpoint already exists: `POST /market/securities/{security_id}/ai/summarize-notes` → `AIService.summarize_notes` (`src/market/ai_service.py`). It gathers up to 50 notes and builds a generic prompt — no recency weighting, and it is currently wired into the "AI Analysis" group, not the Notes group.
- The security page already handles keyboard shortcuts via `svelte:window onkeydown` → `drawingsService.handleKeyDown` (`frontend/src/routes/security/[security_id]/+page.svelte`); the new shortcut must ignore keystrokes while typing in form fields or with modals open.
- No open tickets overlap with this feature; prior feature work uses the same sidebar page (`F-INSTANT-NAVIGATION`, `F-WATCHLIST-MANUAL-SORT`).

## What needs to be done

1. Frontend: `n` shortcut scoped to the security page that opens the note creation dialog (respect typing-in-input and open-modal conditions).
2. Frontend: make the creation dialog content-first (single content field, autofocus).
3. Backend: extend the notes AI summary so recency weighting happens in the prompt (pass note timestamps, instruct proportional weighting toward recent notes), and move generation to a huey background task — dispatched on note create/update/delete, result persisted and fetched via an endpoint (follow `generate_note_title_task` as the pattern).
4. Frontend: summary block at top of the Notes group wired to the latest-summary endpoint, refreshing on note changes with loading/error/retry states.

2 and 4 both touch the Notes group; sequencing 1–2 before 4 avoids merge friction, but 3 is independent of the frontend.

## Open questions

(none — product decisions resolved with the user; see History)

## Definition of done

- [ ] Pressing `n` on the security page opens the note creation dialog, focused on content, unless the user is typing or a modal is open.
- [ ] New notes are created without an explicit title.
- [ ] When a security has notes, the Notes group shows an AI summary at top that mentions/reflects recent notes more strongly.
- [ ] Summary generation is dispatched to a huey task on note create/update/delete; the Notes group shows the persisted latest summary with loading/error+retry states.
