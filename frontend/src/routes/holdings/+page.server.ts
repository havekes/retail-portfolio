import { getAccountService } from '$lib/api/accountService';
import { deleteAuthCookie } from '$lib/server/auth-cookie';
import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import { error, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import { normalizeHoldingsTableConfig } from '$lib/components/holdings/holdings-table-columns';
import { normalizeHoldingsGroupMode } from '$lib/components/holdings/holdings-group-prefs';
import type { UserHolding } from '$lib/types/account';
import type { PageServerLoad } from './$types';

const PAGE_SIZE = 50;
// Safety valve against a stale `total` from the server: never page forever.
const MAX_PAGES = 100;

async function loadAllHoldings(
	fetch: typeof globalThis.fetch,
	token: string | undefined
): Promise<UserHolding[]> {
	const accountService = getAccountService(fetch);
	const collected: UserHolding[] = [];
	let offset = 0;
	let total = Infinity;

	for (let page = 0; page < MAX_PAGES && offset < total; page++) {
		const response = await accountService.getUserHoldings(offset, PAGE_SIZE, token);
		collected.push(...response.items);
		total = response.total;
		offset += PAGE_SIZE;

		if (response.items.length === 0) break;
	}

	return collected;
}

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const token = cookies.get('auth_token');

	try {
		const holdings = await loadAllHoldings(fetch, token);

		// One preferences request for both persisted keys. The client-side helpers
		// are token-less (browser same-origin), so SSR reads the token explicitly.
		let holdings_table_config = normalizeHoldingsTableConfig(null);
		let group_mode = normalizeHoldingsGroupMode(null);
		try {
			const prefs = await getUserPreferencesService(fetch).getPreferences(token);
			holdings_table_config = normalizeHoldingsTableConfig(prefs?.holdings_table);
			group_mode = normalizeHoldingsGroupMode(prefs?.holdings_group);
		} catch {
			// Preferences are non-fatal: fall back to defaults and still render holdings.
		}

		return {
			holdings,
			holdings_table_config,
			group_mode
		};
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 401) {
				deleteAuthCookie(cookies);
				throw redirect(303, '/auth/login?clear_session=true');
			}
			throw error(err.status, err.message);
		}
		throw error(500, 'Internal Server Error');
	}
};
