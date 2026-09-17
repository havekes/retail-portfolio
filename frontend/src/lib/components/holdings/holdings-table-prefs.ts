import type { UserPreferences } from '$lib/api/userPreferencesService';
import { normalizeHoldingsTableConfig, type HoldingsTableConfig } from './holdings-table-columns';

/**
 * Minimal structural view of the preferences service so callers (and tests) can
 * inject any instance without importing the module-level singleton — see the SSR
 * "no global instances" rule in frontend/AGENTS.md.
 */
export type HoldingsTablePrefsService = {
	getPreferences(tokenOverride?: string | null): Promise<UserPreferences>;
	patchPreferences(
		prefs: Partial<UserPreferences>,
		tokenOverride?: string | null
	): Promise<UserPreferences>;
};

/**
 * Loads the persisted `holdings_table` config through the injected service.
 * Tolerates a missing key, an empty `{}` response and thrown requests by falling
 * back to the config defaults.
 */
export async function loadHoldingsTableConfig(
	service: HoldingsTablePrefsService
): Promise<HoldingsTableConfig> {
	try {
		const prefs = await service.getPreferences();
		return normalizeHoldingsTableConfig(prefs?.holdings_table);
	} catch {
		return normalizeHoldingsTableConfig(null);
	}
}

/**
 * Persists the whole config under a single `holdings_table` key so the backend's
 * top-level JSONB merge can't race with other preference writes.
 */
export async function saveHoldingsTableConfig(
	service: HoldingsTablePrefsService,
	config: HoldingsTableConfig
): Promise<void> {
	await service.patchPreferences({ holdings_table: config });
}
