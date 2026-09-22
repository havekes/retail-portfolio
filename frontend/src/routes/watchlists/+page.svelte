<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import { userPreferencesService } from '$lib/api/userPreferencesService';
	import type { WatchlistRead, WatchlistSort } from '$lib/api/marketService';
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Alert, AlertDescription } from '$lib/components/ui/alert/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import CreateWatchlistModal from '$lib/components/watchlist/create-watchlist-modal.svelte';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';
	import {
		formatPrice,
		formatPriceChangePercent,
		normalizeWatchlistSort,
		sortSecurities,
		sortWatchlistsByOrder
	} from '$lib/components/watchlist/watchlist-utils';
	import { cn } from '$lib/utils';
	import { getContext, untrack } from 'svelte';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import Check from '@lucide/svelte/icons/check';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import GripVertical from '@lucide/svelte/icons/grip-vertical';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';

	let {
		data
	}: {
		data: {
			watchlists: WatchlistRead[];
			watchlist_order?: string[] | null;
		};
	} = $props();

	/**
	 * The dropdown contract: `direction` is the visual sense of each mode, used for the
	 * active-option chevron (ChevronUp = ascending/oldest-first, ChevronDown = descending/
	 * newest-first), mirroring the holdings table header indicator.
	 */
	const sortOptions: { value: WatchlistSort; label: string; direction: 'asc' | 'desc' }[] = [
		{ value: 'custom', label: 'Custom', direction: 'asc' },
		{ value: 'name_asc', label: 'Name (alphabetical)', direction: 'asc' },
		{ value: 'price_change_desc', label: 'Price Change (Gainers)', direction: 'desc' },
		{ value: 'price_change_asc', label: 'Price Change (Losers)', direction: 'asc' },
		{ value: 'date_added', label: 'Date added (newest first)', direction: 'desc' },
		{ value: 'date_added_asc', label: 'Date added (oldest first)', direction: 'asc' }
	];

	const watchlistService = getWatchlistService();
	const openGlobalSearch = getContext<((watchlist?: WatchlistRead | null) => void) | undefined>(
		'openGlobalSearch'
	);

	// Safety net only: the server load no longer supplies watchlists (the layout-owned
	// service fetches them asynchronously), so `data.watchlists` is empty and this guard
	// is inert. Kept for direct/programmatic renders that still pass server data.
	if (watchlistService.watchlists.length === 0 && untrack(() => data.watchlists).length > 0) {
		watchlistService.watchlists = untrack(() => data.watchlists);
	}

	let watchlistOrder = $state<string[] | null>(
		untrack(
			() => data.watchlist_order ?? ($page?.data?.watchlist_order as string[] | undefined) ?? null
		)
	);

	const orderedWatchlists = $derived(
		sortWatchlistsByOrder(watchlistService.watchlists ?? [], watchlistOrder)
	);
	const watchlists = $derived(orderedWatchlists);
	const isInitialLoading = $derived(
		watchlistService.isLoading && watchlistService.watchlists.length === 0
	);

	let isReorderMode = $state(false);
	let draggedIndex = $state<number | null>(null);
	let dragOverIndex = $state<number | null>(null);

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
		await watchlistService.deleteWatchlist(watchlistId);
	}

	function countLabel(watchlist: WatchlistRead): string {
		const count = watchlist.securities.length;
		return `${count} ${count === 1 ? 'security' : 'securities'}`;
	}

	async function handleRemoveSecurity(watchlistId: string, securityId: string) {
		await watchlistService.removeSecurityFromWatchlist(watchlistId, securityId);
	}

	async function handleSortSelect(watchlist: WatchlistRead, sort: WatchlistSort) {
		await watchlistService.setSort(watchlist.id, sort);
	}

	function handleDragStart(e: DragEvent, index: number) {
		if (!isReorderMode) return;
		draggedIndex = index;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', String(index));
		}
	}

	function handleDragOver(e: DragEvent, index: number) {
		if (!isReorderMode || draggedIndex === null) return;
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'move';
		}
		dragOverIndex = index;
	}

	function handleDragLeave() {
		dragOverIndex = null;
	}

	async function handleDrop(e: DragEvent, targetIndex: number) {
		if (!isReorderMode || draggedIndex === null) return;
		e.preventDefault();
		const from = draggedIndex;
		draggedIndex = null;
		dragOverIndex = null;

		if (from === targetIndex) return;

		const currentList = [...orderedWatchlists];
		const [moved] = currentList.splice(from, 1);
		currentList.splice(targetIndex, 0, moved);

		watchlistService.watchlists = currentList;
		const newOrder = currentList.map((w) => w.id);
		watchlistOrder = newOrder;

		await userPreferencesService
			.patchPreferences({ watchlist_order: newOrder })
			.catch(console.error);
	}

	function handleDragEnd() {
		draggedIndex = null;
		dragOverIndex = null;
	}

	function getPillClass(changePercent: number | null | undefined): string {
		if (changePercent == null || Number.isNaN(Number(changePercent))) {
			return 'text-muted-foreground bg-muted/40 border-border/40';
		}
		const num = Number(changePercent);
		if (num > 0) {
			return 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
		}
		if (num < 0) {
			return 'text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20';
		}
		return 'text-muted-foreground bg-muted/40 border-border/40';
	}
</script>

<svelte:head>
	<title>Watchlists</title>
</svelte:head>

<div class="flex flex-1 flex-col overflow-hidden bg-background">
	<PageHeader title="Watchlists">
		{#snippet actions()}
			<div class="flex items-center gap-2">
				{#if isReorderMode}
					<Button variant="outline" onclick={() => (isReorderMode = false)}>Done</Button>
				{:else}
					<Button variant="outline" onclick={() => (isReorderMode = true)}>Reorder</Button>
				{/if}
				<Button onclick={() => (createOpen = true)}>Create watchlist</Button>
			</div>
		{/snippet}
	</PageHeader>

	<main class="flex flex-1 flex-col gap-6 overflow-y-auto p-4">
		{#if watchlistService.error && !createOpen}
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
				{#each watchlists as watchlist, index (watchlist.id)}
					<section
						aria-label={`${watchlist.name} securities`}
						class={cn(
							'flex flex-col gap-3 rounded-lg border p-4 transition-colors',
							isReorderMode && 'cursor-move border-dashed select-none',
							dragOverIndex === index && 'border-primary bg-muted/40'
						)}
						draggable={isReorderMode}
						ondragstart={(e) => handleDragStart(e, index)}
						ondragover={(e) => handleDragOver(e, index)}
						ondragleave={handleDragLeave}
						ondrop={(e) => handleDrop(e, index)}
						ondragend={handleDragEnd}
					>
						<div class="flex h-10 min-h-10 items-center justify-between gap-2">
							{#if editingId === watchlist.id}
								<div class="flex items-center gap-2">
									<Input
										bind:value={editingName}
										aria-label="Watchlist name"
										class="h-8 max-w-xs"
										onkeydown={(event) => handleRenameKeydown(event, watchlist)}
									/>
									<Button
										size="icon-sm"
										class="h-8 w-8"
										aria-label={`Save ${watchlist.name}`}
										onclick={() => confirmRename(watchlist)}
									>
										<Check class="h-4 w-4" />
									</Button>
									<Button
										size="icon-sm"
										variant="ghost"
										class="h-8 w-8"
										aria-label="Cancel rename"
										onclick={cancelRename}
									>
										<X class="h-4 w-4" />
									</Button>
								</div>
							{:else}
								<div class="flex items-center gap-2">
									{#if isReorderMode}
										<GripVertical
											class="h-4 w-4 shrink-0 cursor-grab text-muted-foreground"
											data-testid="drag-handle"
											aria-hidden="true"
										/>
									{/if}
									<h2 class="text-lg leading-none font-semibold">{watchlist.name}</h2>
									<span class="text-sm leading-none text-muted-foreground"
										>{countLabel(watchlist)}</span
									>
								</div>
								<div class="flex items-center gap-1">
									<DropdownMenu.Root>
										<DropdownMenu.Trigger>
											{#snippet child({ props })}
												<Button
													{...props}
													size="icon-sm"
													variant="ghost"
													aria-label={`Sort securities in ${watchlist.name}`}
												>
													<ArrowUpDown class="h-4 w-4" />
												</Button>
											{/snippet}
										</DropdownMenu.Trigger>
										<DropdownMenu.Content align="end">
											{#each sortOptions as option (option.value)}
												{@const isActive = normalizeWatchlistSort(watchlist.sort) === option.value}
												<DropdownMenu.Item
													onclick={() => handleSortSelect(watchlist, option.value)}
												>
													<span class="flex-1">{option.label}</span>
													{#if isActive}
														{#if option.direction === 'asc'}
															<ChevronUp size={12} />
														{:else}
															<ChevronDown size={12} />
														{/if}
														<Check class="h-4 w-4" />
													{/if}
												</DropdownMenu.Item>
											{/each}
										</DropdownMenu.Content>
									</DropdownMenu.Root>
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
							{@const sortedSecurities = sortSecurities(
								watchlist.securities,
								normalizeWatchlistSort(watchlist.sort)
							)}
							<ul aria-label={`${watchlist.name} securities list`} class="flex flex-col gap-1">
								{#each sortedSecurities as security (security.id)}
									<li class="flex items-center gap-2">
										<a
											href={resolve(`/security/${security.id}`)}
											class="flex flex-1 items-center justify-between gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted focus:bg-muted"
										>
											<div class="flex min-w-0 items-center gap-2">
												<span class="shrink-0 font-medium">{security.symbol}</span>
												<span class="truncate text-sm text-muted-foreground">{security.name}</span>
											</div>
											<div class="flex shrink-0 items-center gap-2">
												<span class="text-sm font-medium tabular-nums">
													{formatPrice(security.current_price)}
												</span>
												<span
													class={cn(
														'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
														getPillClass(security.daily_price_change_percent)
													)}
												>
													{formatPriceChangePercent(security.daily_price_change_percent)}
												</span>
											</div>
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
