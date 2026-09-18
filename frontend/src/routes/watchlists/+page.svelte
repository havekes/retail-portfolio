<script lang="ts">
	import PageHeader from '@/components/layout/app-header.svelte';
	import { resolve } from '$app/paths';
	import type { WatchlistRead } from '@/api/marketService';
	import { Alert, AlertDescription } from '$lib/components/ui/alert/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import CreateWatchlistModal from '$lib/components/watchlist/create-watchlist-modal.svelte';
	import WatchlistSecurityPicker from '$lib/components/watchlist/watchlist-security-picker.svelte';
	import {
		WATCHLIST_SIDEBAR_PREF,
		type WatchlistSidebarPref
	} from '$lib/components/layout/watchlist-sidebar-pref.js';
	import { getContext, untrack } from 'svelte';
	import Check from '@lucide/svelte/icons/check';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';

	let { data }: { data: { watchlists: WatchlistRead[] } } = $props();

	const watchlistService = getWatchlistService();
	const sidebarPref = getContext<WatchlistSidebarPref | undefined>(WATCHLIST_SIDEBAR_PREF) ?? {
		show: false,
		setShow: () => {}
	};

	// Seed the shared service with the SSR-loaded data so the first paint, the
	// mutations and the sidebar all read from a single source of truth. The
	// layout refreshes the same instance client-side.
	if (watchlistService.watchlists.length === 0 && untrack(() => data.watchlists).length > 0) {
		watchlistService.watchlists = untrack(() => data.watchlists);
	}

	const watchlists = $derived(watchlistService.watchlists);
	const activeWatchlist = $derived(watchlistService.activeWatchlist);
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

	async function handleRemoveSecurity(securityId: string) {
		const active = watchlistService.activeWatchlist;
		if (!active) {
			return;
		}
		watchlistService.error = null;
		await watchlistService.removeSecurity(active.id, securityId);
	}
</script>

<svelte:head>
	<title>Watchlists</title>
</svelte:head>

<div class="flex flex-1 flex-col overflow-hidden bg-background">
	<PageHeader title="Watchlists">
		{#snippet actions()}
			<Button
				variant="outline"
				size="sm"
				aria-label={sidebarPref.show ? 'Hide watchlists in sidebar' : 'Show watchlists in sidebar'}
				aria-pressed={sidebarPref.show}
				onclick={() => sidebarPref.setShow(!sidebarPref.show)}
			>
				{#if sidebarPref.show}
					<EyeOff class="mr-2 h-4 w-4" />
					Hide watchlists
				{:else}
					<Eye class="mr-2 h-4 w-4" />
					Show watchlists
				{/if}
			</Button>
		{/snippet}
	</PageHeader>

	<main class="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
		<div class="flex items-center">
			<Button onclick={() => (createOpen = true)}>Create watchlist</Button>
		</div>

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
			<ul aria-label="Watchlists" class="flex flex-col gap-2">
				{#each watchlists as watchlist (watchlist.id)}
					<li class="flex items-center gap-2 rounded-lg border p-3">
						{#if editingId === watchlist.id}
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
								<Check />
							</Button>
							<Button
								size="icon-sm"
								variant="ghost"
								aria-label="Cancel rename"
								onclick={cancelRename}
							>
								<X />
							</Button>
						{:else}
							<button
								type="button"
								class="font-medium hover:underline"
								aria-pressed={watchlistService.activeWatchlistId === watchlist.id}
								onclick={() => watchlistService.selectWatchlist(watchlist.id)}
							>
								{watchlist.name}
							</button>
							<span class="text-sm text-muted-foreground">{countLabel(watchlist)}</span>
							<div class="ml-auto flex items-center gap-1">
								<Button
									size="icon-sm"
									variant="ghost"
									aria-label={`Rename ${watchlist.name}`}
									onclick={() => startRename(watchlist)}
								>
									<Pencil />
								</Button>
								<Button
									size="icon-sm"
									variant="ghost"
									aria-label={`Delete ${watchlist.name}`}
									onclick={() => requestDelete(watchlist)}
								>
									<Trash2 />
								</Button>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}

		{#if activeWatchlist}
			<section
				aria-label={`${activeWatchlist.name} securities`}
				class="flex flex-col gap-3 rounded-lg border p-4"
			>
				<div class="flex items-center justify-between">
					<h2 class="text-lg font-semibold">{activeWatchlist.name}</h2>
					<span class="text-sm text-muted-foreground">{countLabel(activeWatchlist)}</span>
				</div>

				<WatchlistSecurityPicker watchlistId={activeWatchlist.id} />

				{#if activeWatchlist.securities.length === 0}
					<p class="text-sm text-muted-foreground">No securities in this watchlist yet.</p>
				{:else}
					<ul aria-label="Watchlist securities" class="flex flex-col">
						{#each activeWatchlist.securities as security (security.id)}
							<li class="flex items-center gap-2 border-b py-2 last:border-b-0">
								<a href={resolve(`/security/${security.id}`)} class="font-medium hover:underline">
									{security.symbol}
								</a>
								<span class="truncate text-sm text-muted-foreground">{security.name}</span>
								<Button
									size="icon-sm"
									variant="ghost"
									class="ml-auto"
									aria-label={`Remove ${security.symbol}`}
									onclick={() => handleRemoveSecurity(security.id)}
								>
									<X />
								</Button>
							</li>
						{/each}
					</ul>
				{/if}
			</section>
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
