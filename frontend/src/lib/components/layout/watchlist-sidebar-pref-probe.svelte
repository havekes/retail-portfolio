<script lang="ts">
	import { getContext } from 'svelte';
	import { WATCHLIST_SIDEBAR_PREF, type WatchlistSidebarPref } from './watchlist-sidebar-pref.js';

	// Test-only probe: exposes the layout-provided watchlist sidebar preference so
	// integration tests can read/toggle it without a real page.
	const pref = getContext<WatchlistSidebarPref | undefined>(WATCHLIST_SIDEBAR_PREF);
</script>

<button onclick={() => pref?.setShow(!pref?.show)}>Probe toggle watchlists</button>
<span data-testid="watchlist-pref-state">{pref?.show ? 'on' : 'off'}</span>
