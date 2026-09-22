import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals, fetch, cookies }) => {
	let sidebar_open = true;
	let collapsed_watchlist_ids: string[] = [];
	let watchlist_order: string[] | null = null;

	if (locals.user) {
		const token = cookies.get('auth_token');
		const prefService = getUserPreferencesService(fetch);
		try {
			const prefs = await prefService.getPreferences(token);
			if (prefs && typeof prefs.sidebar_open === 'boolean') {
				sidebar_open = prefs.sidebar_open;
			}
			if (prefs && Array.isArray(prefs.collapsed_watchlist_ids)) {
				collapsed_watchlist_ids = prefs.collapsed_watchlist_ids;
			}
			if (prefs && Array.isArray(prefs.watchlist_order)) {
				watchlist_order = prefs.watchlist_order;
			}
		} catch {
			// Fall back to default open state if preferences request fails
		}
	}

	return {
		user: locals.user,
		sidebar_open,
		collapsed_watchlist_ids,
		watchlist_order
	};
};
