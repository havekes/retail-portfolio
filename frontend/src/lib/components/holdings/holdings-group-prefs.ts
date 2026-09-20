import type { UserPreferences } from '$lib/api/userPreferencesService';
import type { HoldingsGroupMode } from '$lib/utils/finance/holdings-group';

/**
 * Minimal structural view of the preferences service so callers (and tests) can
 * inject any instance without importing the module-level singleton — see the SSR
 * "no global instances" rule in frontend/AGENTS.md.
 */
export type HoldingsGroupPrefsService = {
	getPreferences(tokenOverride?: string | null): Promise<UserPreferences>;
	patchPreferences(
		prefs: Partial<UserPreferences>,
		tokenOverride?: string | null
	): Promise<UserPreferences>;
};

/** Anything that is not explicit `stock` or legacy `company` mode falls back to flat rows. */
export function normalizeHoldingsGroupMode(raw: unknown): HoldingsGroupMode {
	return raw === 'stock' || raw === 'company' ? 'stock' : 'none';
}

/**
 * Loads the persisted `holdings_group` mode through the injected service.
 * Tolerates a missing key, an empty response and thrown requests by falling back
 * to `'none'`.
 */
export async function loadHoldingsGroupMode(
	service: HoldingsGroupPrefsService
): Promise<HoldingsGroupMode> {
	try {
		const prefs = await service.getPreferences();
		return normalizeHoldingsGroupMode(prefs?.holdings_group);
	} catch {
		return 'none';
	}
}

/**
 * Persists the mode under a single `holdings_group` key so the backend's
 * top-level JSONB merge can't race with other preference writes.
 */
export async function saveHoldingsGroupMode(
	service: HoldingsGroupPrefsService,
	mode: HoldingsGroupMode
): Promise<void> {
	await service.patchPreferences({ holdings_group: mode });
}
