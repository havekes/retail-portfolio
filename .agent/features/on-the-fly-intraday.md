---
title: On-the-fly intraday price fetching
slug: on-the-fly-intraday
status: ready
date: 2026-08-06
---

# On-the-fly intraday price fetching

## Problem

Users often see a "No price data available for this timeframe" error when switching to 1-hour or 4-hour charts for a security. This happens because intraday candles are only fetched by a scheduled background job, meaning newly added securities or securities that were missed by the job have no intraday data in the database.

## Goal

Load intraday (1h, 4h) candles dynamically on demand when requested by the client, ensuring the chart always loads even if the background job hasn't fetched the data yet.

## User-facing behavior

When a user views a security chart and selects the "1h" or "4h" timeframe, if the backend doesn't have the data in its database, it will transparently fetch it from the market data provider, save it, and return it. The user might experience a slightly longer loading time during the initial fetch, but the chart will successfully render instead of showing an error state.

## Scope

**In scope:**
- Detecting missing intraday data when the `/market/prices/{security_id}` endpoint is called for `1h` or `4h` intervals.
- Fetching the missing 1h intraday data from the market gateway on the fly.
- Saving the newly fetched data to the database before returning it.
- Aggregating to 4h if that was the requested interval.

**Out of scope:**
- Modifying how daily, weekly, or monthly prices are fetched.
- Changing the behavior of the existing background polling jobs.

## Current state & gap

Currently, when the frontend (`frontend/src/routes/security/[security_id]/+page.svelte`) requests 1h or 4h data, the backend endpoint `market_get_prices` (`src/market/router.py`) simply queries `IntradayPriceRepository.get_intraday_prices`. If no data is found, it returns an empty list, triggering the frontend's error state.

While `MarketService` (`src/market/service.py`) has a `update_intraday_prices_for_all_securities` method for background jobs, it lacks a dedicated on-the-fly fetch method for a single security (similar to `fetch_and_save_price_history` which handles daily prices upon security creation).

## What needs to be done

- Add an on-demand intraday fetching capability to `MarketService` that fetches the last N days (e.g. 7 or 30 days) of 1h candles for a specific security and saves them to the repository.
- Wire this up in the `market_get_prices` router endpoint: if the initial database query for intraday candles returns empty (or is completely missing data for the requested range), invoke the `MarketService` fetch method, then re-query the repository to serve the newly loaded data.

## Open questions

- **Date range for on-the-fly fetch:** How much intraday history should we fetch on the fly? 
  *Default:* We will fetch the last 30 days to provide enough data for a meaningful chart while keeping API request sizes reasonable.

## Definition of done

- [ ] A user can add a completely new security, immediately switch to the 1h or 4h chart, and successfully see the price candles without encountering the "No price data" error.
