import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

// Neither the security identity nor its price series is awaited here: the page
// fetches both after navigation (see `page-data.svelte.ts`) so the shell and
// titlebar render instantly. Only the cheap route identity comes from the server.
export const load: PageServerLoad = async ({ params }) => {
	const { security_id } = params;

	if (!security_id) {
		throw error(400, 'Security ID is required');
	}

	return { security_id };
};
