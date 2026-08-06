---
title: User chart preferences
slug: user-chart-preferences
status: ready
date: 2026-08-06
---

# User chart preferences

## Problem

The security details chart forgets the user's setup on every visit. The timeframe always resets to `1d` (there is no persistence for it at all), the chart rendering is hardcoded to Heikin-Ashi with no style control, and indicator toggles are stored **per security** in a separate table — so a user who wants MA50 + RSI on every chart must re-enable them per security, and the per-security storage is currently only half-wired anyway (the frontend load path was just fixed in BUG-1 #154; the save call is commented out).

## Goal

One global set of chart settings per user — timeframe, chart style, and indicator config — stored as a user-level preference and applied to the security details chart no matter which security is open. Per-security preference storage is removed.

## User-facing behavior

- On the security details page, the user selects a timeframe (`1h` / `4h` / `1d` / `1w` / `1m`), a chart style, and toggles/configures indicators (MA, RSI, MACD, Bollinger Bands, OBV, Volume, Avg Price).
- The user navigates away and later returns to the **same or a different** security: the same timeframe, chart style, and indicator settings are restored immediately.
- Users with no saved preferences get the current defaults: timeframe `1d`, the existing Heikin-Ashi rendering, and today's default indicator state (all indicators off except Avg Price, which stays on).
- Changing settings on one security updates the global preference; the change is visible on all other securities on the next load.
- The user's saved preferences survive sign-out/sign-in (server-side storage) and work across devices.

## Scope

**In scope:**
- A JSON preference field on the user record holding chart settings (timeframe, chart style, indicator config).
- Persisting the timeframe selection.
- A chart style setting (Heikin-Ashi / Candlestick), with a control to change it and current rendering (Heikin-Ashi) as the default.
- Persisting indicator toggle state **and** per-indicator config (period, stdDev, MACD fast/slow/signal, color) at the user level.
- Removing the per-security indicator-preferences storage, API, and frontend wiring.
- Updating the OpenSpec `technical-indicators` "Indicator persistence" requirement (currently "per security").

**Out of scope:**
- Per-security chart settings of any kind (deliberately gone; preferences are user-global only).
- Watchlist, price alerts, notes, documents, AI analysis, holdings sidebar state — unrelated to chart settings.
- Migrating existing `market_indicator_preferences` rows (decision: existing per-security rows are discarded on removal).
- Schema/UX changes for anything other than the security chart's settings (timeframe, style, indicators).

## Current state & gap

- **Timeframe:** `frontend/src/routes/security/[security_id]/+page.svelte` — `selectedInterval = $state('1d')` is never persisted; it resets on every visit. No chart-style setting exists; `convertToHeikinAshi` is applied unconditionally.
- **Indicator toggles (today, per-security):**
  - `src/market/model.py` (L197–212) — `IndicatorPreferencesModel`, table `market_indicator_preferences`, JSON column `indicators_json`, unique on `(security_id, user_id)`.
  - `src/market/router.py` (L573–600) — `GET` / `PUT /securities/{security_id}/indicator-preferences`.
  - `src/market/repository_sqlalchemy.py` (L865) — `sqlalchemy_indicator_preferences_repository_factory`.
  - Frontend: `frontend/src/lib/api/indicatorsService.ts` (`getPreferences` / `savePreferences`) and `frontend/src/lib/components/actions-sidebar/indicator/indicator-group.svelte` (loads prefs per security; the `savePreferences` call is commented out).
- **User record:** `src/auth/model.py` — `UserModel` (`auth_users`) has no preferences column today; it owns the user record that would carry the new JSON field.
- **In-flight overlap:** BUG-1 (#154, `status: approved`, branch `feat/bug-1-fix-indicator-preferences`) fixes the per-security endpoint wiring (PUT verb + `/market` prefix). It becomes obsolete once the per-security endpoint is removed — supersede/close it as part of this work.
- **Blueprint:** `openspec/specs/technical-indicators/spec.md` requires "Indicator persistence … per security"; this feature changes that scope to user-global.

## What needs to be done

1. **User preferences storage** — add a `preferences` JSON column to `auth_users` (alembic migration) with a user preferences API (GET / PUT) exposed through the auth/account domain. Hard prerequisite for everything else.
2. **Frontend chart settings** — persist `selectedInterval` and a new chart-style setting into the user preference; apply saved values on chart load; add the style control to the security page.
3. **Indicator prefs at user level** — replace per-security load/save with the user-level preference; restore toggles and per-indicator config globally.
4. **Remove per-security storage** — drop `market_indicator_preferences` (migration), delete its repository/router/factory code and the frontend `indicatorsService` per-security methods; supersede/close BUG-1 #154.
5. **Blueprint update** — revise the `technical-indicators` persistence requirement to user-global.

## Definition of done

- [ ] A user's timeframe selection persists across visits and applies to any security's chart.
- [ ] A user's chart style selection persists and applies to any security's chart.
- [ ] Indicator toggles and per-indicator config are user-global — enabled once, applied to every security chart.
- [ ] `market_indicator_preferences` table, its endpoints, and per-security frontend wiring are removed; BUG-1 #154 is superseded/closed.
- [ ] The OpenSpec `technical-indicators` persistence requirement reflects user-global (not per-security) persistence.
