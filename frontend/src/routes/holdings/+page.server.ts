import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import { normalizeHoldingsTableConfig } from '$lib/components/holdings/holdings-table-columns';
import { normalizeHoldingsGroupMode } from '$lib/components/holdings/holdings-group-prefs';
import { getPortfolioClient } from '$lib/api/portfolioClient';
import { getAccountClient } from '$lib/api/accountClient';
import { deleteAuthCookie } from '$lib/server/auth-cookie';
import { ApiError } from '$lib/api/apiClient';
import { redirect } from '@sveltejs/kit';
import type { Portfolio } from '$lib/types/portfolio';
import type { Account } from '$lib/types/account';
import type { SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
	const token = cookies.get('auth_token');
	const portfolio_id = url.searchParams.get('portfolio_id');
	const account_id = url.searchParams.get('account_id');

	// Only the cheap, preferences, portfolios, and accounts keys are awaited: holdings rows load
	// asynchronously after navigation so the page shell renders instantly.
	let holdings_table_config = normalizeHoldingsTableConfig(null);
	let group_mode = normalizeHoldingsGroupMode(null);
	let elliott_waves: Record<string, SecurityElliottWaves> | null = null;
	let portfolios: Portfolio[] = [];
	let accounts: Account[] = [];

	try {
		const [prefsResult, portfoliosResult, accountsResult] = await Promise.allSettled([
			getUserPreferencesService(fetch).getPreferences(token),
			getPortfolioClient(fetch).getPortfolios(token),
			getAccountClient(fetch).getAccounts(token)
		]);

		for (const res of [prefsResult, portfoliosResult, accountsResult]) {
			if (
				res.status === 'rejected' &&
				res.reason instanceof ApiError &&
				res.reason.status === 401
			) {
				deleteAuthCookie(cookies);
				throw redirect(303, '/auth/login?clear_session=true');
			}
		}

		if (prefsResult.status === 'fulfilled') {
			const prefs = prefsResult.value;
			holdings_table_config = normalizeHoldingsTableConfig(prefs?.holdings_table);
			group_mode = normalizeHoldingsGroupMode(prefs?.holdings_group);
			elliott_waves = prefs?.elliott_waves ?? null;
		}

		if (portfoliosResult.status === 'fulfilled') {
			portfolios = portfoliosResult.value;
		}

		if (accountsResult.status === 'fulfilled') {
			accounts = accountsResult.value;
		}
	} catch (err) {
		if (
			err &&
			typeof err === 'object' &&
			'status' in err &&
			(err as { status: number }).status === 303
		) {
			throw err;
		}
	}

	return {
		holdings_table_config,
		group_mode,
		elliott_waves,
		portfolios,
		accounts,
		portfolio_id,
		account_id
	};
};
