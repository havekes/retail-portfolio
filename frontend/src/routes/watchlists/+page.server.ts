import type { PageServerLoad } from './$types';

// The watchlists themselves are NOT awaited here: the layout-owned
// `WatchlistService.loadWatchlists()` (see `+layout.svelte`) is the single owner of
// the initial fetch, so `/watchlists` renders its titlebar, actions and skeleton
// rows instantly. An empty list keeps the `data.watchlists` prop shape intact for
// the page's seeding guard, which is inert while this stays empty.
export const load: PageServerLoad = () => {
	return { watchlists: [] };
};
