<script lang="ts">
	import Layout from './+layout.svelte';
	import WatchlistSidebarPrefProbe from '$lib/components/layout/watchlist-sidebar-pref-probe.svelte';

	let { data } = $props();
</script>

<Layout {data}>
	<WatchlistSidebarPrefProbe />
</Layout>
