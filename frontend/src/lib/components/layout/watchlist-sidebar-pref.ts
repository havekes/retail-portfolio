/**
 * Context key and contract for the "show watchlists in the sidebar" preference.
 *
 * The root layout owns the reactive state and persistence; the sidebar and the
 * `/watchlists` page both read/write it through this context so the toggle can
 * live on the page without prop-drilling it through the layout.
 */
export const WATCHLIST_SIDEBAR_PREF = Symbol('watchlist-sidebar-pref');

export interface WatchlistSidebarPref {
	/** Reactive getter — reads the layout's `$state`, so consumers stay in sync. */
	readonly show: boolean;
	/** Persists the preference and updates the shared state. */
	setShow(value: boolean): void;
}
