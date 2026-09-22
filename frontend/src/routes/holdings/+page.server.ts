import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import { normalizeHoldingsTableConfig } from '$lib/components/holdings/holdings-table-columns';
import { normalizeHoldingsGroupMode } from '$lib/components/holdings/holdings-group-prefs';
import type { SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const token = cookies.get('auth_token');

	// Only the cheap, preferences-derived keys are awaited: holdings rows load
	// asynchronously after navigation so the page shell renders instantly.
	// The client-side helpers are token-less (browser same-origin), so SSR reads
	// the token explicitly.
	let holdings_table_config = normalizeHoldingsTableConfig(null);
	let group_mode = normalizeHoldingsGroupMode(null);
	let elliott_waves: Record<string, SecurityElliottWaves> | null = null;
	try {
		const prefs = await getUserPreferencesService(fetch).getPreferences(token);
		holdings_table_config = normalizeHoldingsTableConfig(prefs?.holdings_table);
		group_mode = normalizeHoldingsGroupMode(prefs?.holdings_group);
		elliott_waves = prefs?.elliott_waves ?? null;
	} catch {
		// Preferences are non-fatal: fall back to defaults and still render holdings.
	}

	return {
		holdings_table_config,
		group_mode,
		elliott_waves
	};
};
