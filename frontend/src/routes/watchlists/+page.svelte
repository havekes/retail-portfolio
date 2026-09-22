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
		formatDateAdded,
		formatPrice,
		formatPriceChangePercent,
		handleReorderKeydown,
		moveItem,
		normalizeWatchlistSort,
		sortSecurities,
		sortWatchlistsByOrder,
		WATCHLIST_ROW_DATA_TRACKS
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

	// Security reordering is offered per watchlist (one active list at a time) and
	// only for custom-sorted lists, where the row order maps onto `position`.
	let securityReorderWatchlistId = $state<string | null>(null);
	let securityDragIndex = $state<number | null>(null);
	let securityDragOverIndex = $state<number | null>(null);

	let announcement = $state('');

	function announce(text: string) {
		announcement = text;
	}

	let editingId = $state<string | null>(null);
	let editingName = $state('');
	let deleteOpen = $state(false);
	let createOpen = $state(false);
	let pendingDelete = $state<WatchlistRead | null>(null);

	// Row selection is focus-driven: the highlighted row is the security that
	// currently holds keyboard focus, remembered per watchlist id. Keyed by
	// security id (not row index) so the highlight follows the same security
	// through arrow-key/drag reorder and sort changes, and survives blur.
	let selectedByWatchlistId = $state<Record<string, string>>({});

	function selectRow(watchlistId: string, securityId: string) {
		selectedByWatchlistId[watchlistId] = securityId;
	}

	function isRowSelected(watchlistId: string, securityId: string): boolean {
		return selectedByWatchlistId[watchlistId] === securityId;
	}

	/** Drop a remembered selection so a removed security cannot stay highlighted. */
	function clearSelection(watchlistId: string) {
		if (watchlistId in selectedByWatchlistId) {
			delete selectedByWatchlistId[watchlistId];
		}
	}

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
		clearSelection(watchlistId);
	}

	function countLabel(watchlist: WatchlistRead): string {
		const count = watchlist.securities.length;
		return `${count} ${count === 1 ? 'security' : 'securities'}`;
	}

	async function handleRemoveSecurity(watchlistId: string, securityId: string) {
		await watchlistService.removeSecurityFromWatchlist(watchlistId, securityId);
		if (selectedByWatchlistId[watchlistId] === securityId) {
			clearSelection(watchlistId);
		}
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

	/**
	 * Move a watchlist one slot, applying the new order optimistically and
	 * persisting `watchlist_order`. On failure both local snapshots are restored so
	 * no stale order survives, and the error surfaces in the shared alert. Used by
	 * both the drag-and-drop and keyboard paths so the two stay in lockstep.
	 */
	async function moveWatchlist(from: number, to: number) {
		if (!isReorderMode || from === to) return;

		const currentList = [...orderedWatchlists];
		const moved = currentList[from];
		if (!moved) return;

		const previousOrder = watchlistOrder;
		const previousWatchlists = watchlistService.watchlists;

		const nextList = moveItem(currentList, from, to);
		const newOrder = nextList.map((w) => w.id);
		watchlistService.watchlists = nextList;
		watchlistOrder = newOrder;
		announce(`${moved.name} moved to position ${to + 1} of ${nextList.length}`);

		try {
			await userPreferencesService.patchPreferences({ watchlist_order: newOrder });
		} catch (err) {
			watchlistService.watchlists = previousWatchlists;
			watchlistOrder = previousOrder;
			watchlistService.error =
				err instanceof Error ? err.message : 'Failed to save watchlist order';
		}
	}

	async function handleDrop(e: DragEvent, targetIndex: number) {
		if (!isReorderMode || draggedIndex === null) return;
		e.preventDefault();
		const from = draggedIndex;
		draggedIndex = null;
		dragOverIndex = null;

		await moveWatchlist(from, targetIndex);
	}

	function handleDragEnd() {
		draggedIndex = null;
		dragOverIndex = null;
	}

	function isSecurityReorderEnabled(watchlist: WatchlistRead): boolean {
		return (
			normalizeWatchlistSort(watchlist.sort) === 'custom' &&
			securityReorderWatchlistId === watchlist.id
		);
	}

	/** Security drag only applies when its list's toggle is on and watchlist reorder mode is off. */
	function isSecurityReorderActive(watchlist: WatchlistRead): boolean {
		return isSecurityReorderEnabled(watchlist) && !isReorderMode;
	}

	function toggleSecurityReorder(watchlist: WatchlistRead) {
		securityReorderWatchlistId = securityReorderWatchlistId === watchlist.id ? null : watchlist.id;
		securityDragIndex = null;
		securityDragOverIndex = null;
	}

	function sortedSecuritiesFor(watchlist: WatchlistRead) {
		return sortSecurities(watchlist.securities, normalizeWatchlistSort(watchlist.sort));
	}

	/** Reorder a security, persist the new id order and announce the completed move. */
	function moveSecurity(watchlist: WatchlistRead, from: number, to: number) {
		if (!isSecurityReorderActive(watchlist) || from === to) return;

		const sorted = sortedSecuritiesFor(watchlist);
		const moved = sorted[from];
		if (!moved) return;

		const securityIds = moveItem(sorted, from, to).map((s) => s.id);
		announce(`${moved.symbol} moved to position ${to + 1} of ${sorted.length}`);
		void watchlistService.reorderSecurities(watchlist.id, securityIds);
	}

	function handleSecurityDragStart(e: DragEvent, watchlist: WatchlistRead, index: number) {
		if (!isSecurityReorderActive(watchlist)) return;
		securityDragIndex = index;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', String(index));
		}
	}

	function handleSecurityDragOver(e: DragEvent, watchlist: WatchlistRead, index: number) {
		if (!isSecurityReorderActive(watchlist) || securityDragIndex === null) return;
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'move';
		}
		securityDragOverIndex = index;
	}

	function handleSecurityDragLeave() {
		securityDragOverIndex = null;
	}

	function handleSecurityDrop(e: DragEvent, watchlist: WatchlistRead, targetIndex: number) {
		if (!isSecurityReorderActive(watchlist) || securityDragIndex === null) return;
		e.preventDefault();
		const from = securityDragIndex;
		securityDragIndex = null;
		securityDragOverIndex = null;

		moveSecurity(watchlist, from, targetIndex);
	}

	function handleSecurityDragEnd() {
		securityDragIndex = null;
		securityDragOverIndex = null;
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
		<div role="status" aria-live="polite" class="sr-only">{announcement}</div>

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
							'flex flex-col gap-3 rounded-lg bg-muted p-4 transition-colors',
							isReorderMode && 'cursor-move outline-1 outline-border outline-dashed select-none',
							dragOverIndex === index && 'ring-2 ring-primary'
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
										<button
											type="button"
											data-testid="drag-handle"
											aria-label={`Reorder ${watchlist.name}`}
											class="shrink-0 cursor-grab rounded-sm text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
											onkeydown={(e) =>
												handleReorderKeydown(e, index, watchlists.length, moveWatchlist)}
										>
											<GripVertical class="h-4 w-4" />
										</button>
									{/if}
									<h2 class="text-lg leading-none font-semibold">{watchlist.name}</h2>
									<span class="text-sm leading-none text-muted-foreground"
										>{countLabel(watchlist)}</span
									>
								</div>
								<div class="flex items-center gap-1">
									{#if normalizeWatchlistSort(watchlist.sort) === 'custom'}
										<Button
											size="icon-sm"
											variant={securityReorderWatchlistId === watchlist.id ? 'secondary' : 'ghost'}
											aria-label={`Reorder securities in ${watchlist.name}`}
											aria-pressed={securityReorderWatchlistId === watchlist.id}
											onclick={() => toggleSecurityReorder(watchlist)}
										>
											<GripVertical class="h-4 w-4" />
										</Button>
									{/if}
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
															<ChevronUp size={12} aria-hidden="true" />
														{:else}
															<ChevronDown size={12} aria-hidden="true" />
														{/if}
														<Check class="h-4 w-4" aria-hidden="true" />
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
								{#each sortedSecurities as security, securityIndex (security.id)}
									{@const securityReorderActive = isSecurityReorderActive(watchlist)}
									{@const rowSelected = isRowSelected(watchlist.id, security.id)}
									<li
										aria-current={rowSelected ? 'true' : undefined}
										class={cn(
											'flex items-center gap-2 rounded-md',
											securityReorderActive && 'cursor-move',
											securityReorderActive &&
												securityDragOverIndex === securityIndex &&
												'bg-background/60'
										)}
										draggable={securityReorderActive}
										ondragstart={(e) => handleSecurityDragStart(e, watchlist, securityIndex)}
										ondragover={(e) => handleSecurityDragOver(e, watchlist, securityIndex)}
										ondragleave={handleSecurityDragLeave}
										ondrop={(e) => handleSecurityDrop(e, watchlist, securityIndex)}
										ondragend={handleSecurityDragEnd}
									>
										{#if securityReorderActive}
											<button
												type="button"
												data-testid="security-drag-handle"
												aria-label={`Reorder ${security.symbol}`}
												class="shrink-0 cursor-grab rounded-sm text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
												onkeydown={(e) =>
													handleReorderKeydown(
														e,
														securityIndex,
														sortedSecurities.length,
														(from, to) => moveSecurity(watchlist, from, to)
													)}
											>
												<GripVertical class="h-4 w-4" />
											</button>
										{/if}
										<a
											href={resolve(`/security/${security.id}`)}
											aria-label={`${security.symbol} — ${security.name}`}
											onfocus={() => selectRow(watchlist.id, security.id)}
											class={cn(
												WATCHLIST_ROW_DATA_TRACKS,
												'flex-1 items-center rounded-md px-2 py-1.5 transition-colors',
												'hover:bg-background/60 focus:bg-background/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
												rowSelected && 'bg-background ring-1 ring-ring'
											)}
										>
											<div class="flex min-w-0 items-center gap-2">
												<span class="shrink-0 font-medium">{security.symbol}</span>
												<span class="truncate text-sm text-muted-foreground">{security.name}</span>
											</div>
											<span
												class="hidden truncate text-xs text-muted-foreground md:block"
												title="Added"
											>
												{formatDateAdded(security.added_at) ?? '-'}
											</span>
											<span class="justify-self-end text-sm font-medium tabular-nums">
												{formatPrice(security.current_price)}
											</span>
											<span
												class={cn(
													'inline-flex min-w-[4.5rem] items-center justify-center justify-self-end rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
													getPillClass(security.daily_price_change_percent)
												)}
											>
												{formatPriceChangePercent(security.daily_price_change_percent)}
											</span>
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
