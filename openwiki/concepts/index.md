# Files

- [Money & Currency Handling](money-and-currency.md) - The cross-cutting money model behind totals, holdings, P&L, and CSV import — backend Decimal plus stockholm Money/Currency in API types, per-account/position currency with CurrencyConverter aggregation, the frontend Money shape and its formatting helpers, average-cost and holdings math, and the rounding/mixed-currency pitfalls to avoid when changing any of it.
- [User Preferences & Cross-Session State](user-preferences.md) - The per-user preference contract on GET/PUT/PATCH /accounts/me/preferences — the JSON column and top-level JSONB merge semantics, which component reads and writes each key, exclude_none and write-failure fallbacks, and the fallback defaults applied on read.
