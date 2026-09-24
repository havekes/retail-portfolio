# Files

- [Money & Currency Handling](money-and-currency.md) - The cross-cutting money model behind totals, holdings, P&L, and CSV import — backend Decimal plus stockholm Money/Currency in API types, per-account/position currency with CurrencyConverter aggregation, the frontend Money shape and its formatting helpers, average-cost and holdings math, and the rounding/mixed-currency pitfalls to avoid when changing any of it.
- [User Preferences](user-preferences.md) - The cross-cutting per-user preferences contract — one permissive JSON column on auth_users, the GET/PUT/PATCH /accounts/me/preferences surface with exclude_none and top-level JSONB merge semantics, the complete read/write ownership matrix for every preference key, and the fire-and-forget versus surfaced failure split.
