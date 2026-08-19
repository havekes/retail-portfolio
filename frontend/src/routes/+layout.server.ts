import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals, fetch, cookies }) => {
	let sidebar_open = true;

	if (locals.user) {
		const token = cookies.get('auth_token');
		const prefService = getUserPreferencesService(fetch);
		try {
			const prefs = await prefService.getPreferences(token);
			if (prefs && typeof prefs.sidebar_open === 'boolean') {
				sidebar_open = prefs.sidebar_open;
			}
		} catch {
			// Fall back to default open state if preferences request fails
		}
	}

	return {
		user: locals.user,
		sidebar_open
	};
};
