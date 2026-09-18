<script lang="ts">
	import { resolve } from '$app/paths';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { WatchlistRead } from '$lib/api/marketService';
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Alert, AlertDescription } from '$lib/components/ui/alert/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import CreateWatchlistModal from '$lib/components/watchlist/create-watchlist-modal.svelte';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';
	import { getContext, untrack } from 'svelte';
	import Check from '@lucide/svelte/icons/check';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';

	let { data }: { data: { watchlists: WatchlistRead[] } } = $props();

	const watchlistService = getWatchlistService();
	const openGlobalSearch = getContext<((watchlist?: WatchlistRead | null) => void) | undefined>(
		'openGlobalSearch'
	);

	if (watchlistService.watchlists.length === 0 && untrack(() => data.watchlists).length > 0) {
		watchlistService.watchlists = untrack(() => data.watchlists);
	}

	const watchlists = $derived(watchlistService.watchlists ?? []);
	const isInitialLoading = $derived(
		watchlistService.isLoading && watchlistService.watchlists.length === 0
	);

	let editingId = $state<string | null>(null);
	let editingName = $state('');
	let deleteOpen = $state(false);
	let createOpen = $state(false);
	let pendingDelete = $state<WatchlistRead | null>(null);

	function startRename(watchlist: WatchlistRead) {
		editingId = watchlist.id;
		editingName = watchlist.name;
	}

	function cancelRename() {
		editingId = null;
		editingName = '';
	}

	async function confirmRename(watchlist: WatchlistRead) {
		const name = editingName.trim();
		if (!name || name === watchlist.name) {
			cancelRename();
			return;
		}
		watchlistService.error = null;
		await watchlistService.renameWatchlist(watchlist.id, name);
		if (!watchlistService.error) {
			cancelRename();
		}
	}

	function handleRenameKeydown(event: KeyboardEvent, watchlist: WatchlistRead) {
		if (event.key === 'Enter') {
			event.preventDefault();
			void confirmRename(watchlist);
		} else if (event.key === 'Escape') {
			cancelRename();
		}
	}

	function requestDelete(watchlist: WatchlistRead) {
		pendingDelete = watchlist;
		deleteOpen = true;
	}

	async function confirmDelete() {
		if (!pendingDelete) {
			return;
		}
		const watchlistId = pendingDelete.id;
		pendingDelete = null;
		watchlistService.error = null;
		await watchlistService.deleteWatchlist(watchlistId);
	}

	function countLabel(watchlist: WatchlistRead): string {
		const count = watchlist.securities.length;
		return `${count} ${count === 1 ? 'security' : 'securities'}`;
	}

	async function handleRemoveSecurity(watchlistId: string, securityId: string) {
		watchlistService.error = null;
		await watchlistService.removeSecurityFromWatchlist(watchlistId, securityId);
	}
</script>

<svelte:head>
	<title>Watchlists</title>
</svelte:head>

<div class="flex flex-1 flex-col overflow-hidden bg-background">
	<PageHeader title="Watchlists">
		{#snippet actions()}
			<Button onclick={() => (createOpen = true)}>Create watchlist</Button>
		{/snippet}
	</PageHeader>

	<main class="flex flex-1 flex-col gap-6 overflow-y-auto p-4">
		{#if watchlistService.error}
			<Alert variant="destructive">
				<AlertDescription>{watchlistService.error}</AlertDescription>
			</Alert>
		{/if}

		{#if isInitialLoading}
			<div role="status" aria-label="Loading watchlists" class="flex flex-col gap-2">
				{#each [1, 2, 3] as row (row)}
					<Skeleton class="h-12 w-full" />
				{/each}
			</div>
		{:else if watchlists.length === 0}
			<div class="flex flex-col items-center gap-1 rounded-lg border border-dashed p-8 text-center">
				<p class="text-sm font-medium">You don't have any watchlists yet</p>
				<p class="text-sm text-muted-foreground">Create one above to start tracking securities.</p>
			</div>
		{:else}
			<div class="flex flex-col gap-6">
				{#each watchlists as watchlist (watchlist.id)}
					<section
						aria-label={`${watchlist.name} securities`}
						class="flex flex-col gap-3 rounded-lg border p-4"
					>
						<div class="flex items-center justify-between">
							{#if editingId === watchlist.id}
								<div class="flex items-center gap-2">
									<Input
										bind:value={editingName}
										aria-label="Watchlist name"
										class="max-w-xs"
										onkeydown={(event) => handleRenameKeydown(event, watchlist)}
									/>
									<Button
										size="icon-sm"
										aria-label={`Save ${watchlist.name}`}
										onclick={() => confirmRename(watchlist)}
									>
										<Check class="h-4 w-4" />
									</Button>
									<Button
										size="icon-sm"
										variant="ghost"
										aria-label="Cancel rename"
										onclick={cancelRename}
									>
										<X class="h-4 w-4" />
									</Button>
								</div>
							{:else}
								<div class="flex items-center gap-2">
									<h2 class="text-lg font-semibold">{watchlist.name}</h2>
									<span class="text-sm text-muted-foreground">{countLabel(watchlist)}</span>
								</div>
								<div class="flex items-center gap-1">
									<Button
										size="icon-sm"
										variant="ghost"
										aria-label={`Add security to ${watchlist.name}`}
										onclick={() => openGlobalSearch?.(watchlist)}
									>
										<Plus class="h-4 w-4" />
									</Button>
									<Button
										size="icon-sm"
										variant="ghost"
										aria-label={`Rename ${watchlist.name}`}
										onclick={() => startRename(watchlist)}
									>
										<Pencil class="h-4 w-4" />
									</Button>
									<Button
										size="icon-sm"
										variant="ghost"
										aria-label={`Delete ${watchlist.name}`}
										onclick={() => requestDelete(watchlist)}
									>
										<Trash2 class="h-4 w-4" />
									</Button>
								</div>
							{/if}
						</div>

						{#if watchlist.securities.length === 0}
							<p class="text-sm text-muted-foreground">No securities in this watchlist yet.</p>
						{:else}
							<ul aria-label={`${watchlist.name} securities list`} class="flex flex-col gap-1">
								{#each watchlist.securities as security (security.id)}
									<li class="flex items-center gap-2">
										<a
											href={resolve(`/security/${security.id}`)}
											class="flex flex-1 items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted focus:bg-muted"
										>
											<span class="font-medium">{security.symbol}</span>
											<span class="truncate text-sm text-muted-foreground">{security.name}</span>
										</a>
										<Button
											size="icon-sm"
											variant="ghost"
											aria-label={`Remove ${security.symbol}`}
											onclick={() => handleRemoveSecurity(watchlist.id, security.id)}
										>
											<X class="h-4 w-4" />
										</Button>
									</li>
								{/each}
							</ul>
						{/if}
					</section>
				{/each}
			</div>
		{/if}
	</main>

	<ConfirmationModal
		bind:open={deleteOpen}
		title="Delete watchlist"
		description={pendingDelete
			? `Delete "${pendingDelete.name}"? This cannot be undone.`
			: 'Delete this watchlist?'}
		onconfirm={confirmDelete}
		oncancel={() => (pendingDelete = null)}
	/>

	<CreateWatchlistModal bind:open={createOpen} />
</div>
