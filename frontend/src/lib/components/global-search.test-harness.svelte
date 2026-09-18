<script lang="ts">
	import GlobalSearch from './global-search.svelte';
	import type { WatchlistRead } from '@/api/marketService';
	import { untrack } from 'svelte';

	let {
		initialOpen = false,
		initialTarget = null
	}: {
		initialOpen?: boolean;
		initialTarget?: WatchlistRead | null;
	} = $props();

	let open = $state(untrack(() => initialOpen));
	let targetWatchlist = $state<WatchlistRead | null>(untrack(() => initialTarget));
</script>

<GlobalSearch bind:open bind:targetWatchlist />
<button onclick={() => (open = true)}>Open search</button>
<button onclick={() => (open = false)}>Close search</button>
<span data-testid="target-name">{targetWatchlist?.name ?? 'none'}</span>
