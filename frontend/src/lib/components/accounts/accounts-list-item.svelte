<script lang="ts">
	import { getAccountTypeLabel, getInstitutionLabel, type Account } from '@/types/account';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import EditableTitle from '../forms/editable-title.svelte';
	import Skeleton from '../ui/skeleton/skeleton.svelte';
	import { money } from '@/types/money';
	import * as Tooltip from '../ui/tooltip';
	import { buttonVariants } from '../ui/button';
	import { AccountsListItemState } from './accounts-list-item.svelte.js';
	import { ModalState } from '@/utils/modal-state.svelte';
	import UpdateAccountCsvModal from './update-account-csv-modal.svelte';
	import AccountInlineHoldings from './account-inline-holdings.svelte';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import ConfirmationModal from '../ui/confirmation-modal/confirmation-modal.svelte';
	import EllipsisVertical from '@lucide/svelte/icons/ellipsis-vertical';
	import { Button } from '../ui/button';
	import { formatRelativeSyncTime } from '$lib/utils/date';

	let {
		account,
		selectionMode,
		isSelected,
		onToggleSelection,
		isSyncing,
		onSync,
		syncError,
		onRename,
		onAccountUpdated,
		onDelete
	}: {
		account: Account;
		selectionMode?: boolean;
		isSelected?: boolean;
		onToggleSelection?: () => void;
		isSyncing?: boolean;
		onSync?: () => void;
		syncError?: string | null;
		onRename?: (name: string) => void;
		onAccountUpdated?: () => void;
		onDelete?: () => void;
	} = $props();

	const itemState = new AccountsListItemState(() => account.id);
	const csvModalState = new ModalState<void>();
	let showDeleteModal = $state(false);
	let localSyncOverride = $state<Date | null>(null);
	const effectiveLastSyncAt = $derived(localSyncOverride ?? account.last_sync_at);
	let lastKnownSyncAt: Date | string | null | undefined;
	let wasSyncing = false;

	$effect(() => {
		if (account.last_sync_at !== lastKnownSyncAt) {
			lastKnownSyncAt = account.last_sync_at;
			localSyncOverride = null;
		}
	});

	$effect(() => {
		if (wasSyncing && !isSyncing) {
			itemState.invalidateCache(account.id);
			if (!syncError) {
				localSyncOverride = new Date();
			}
		}
		wasSyncing = isSyncing ?? false;
	});
</script>

<div class="account-list-item group px flex space-x-4 rounded-lg bg-muted p-4">
	{#if selectionMode}
		<div class="flex border-r py-2 pr-4">
			<div class="m-auto">
				<Checkbox class="cursor-pointer" checked={isSelected} onCheckedChange={onToggleSelection} />
			</div>
		</div>
	{/if}

	<div class="flex-1 space-y-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-1">
				<Button
					variant="ghost"
					size="icon"
					class="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
					aria-label={itemState.isExpanded ? 'Collapse holdings' : 'Expand holdings'}
					aria-expanded={itemState.isExpanded}
					onclick={() => itemState.toggleExpanded()}
				>
					{#if itemState.isExpanded}
						<ChevronDown class="h-4 w-4" />
					{:else}
						<ChevronRight class="h-4 w-4" />
					{/if}
				</Button>
				<EditableTitle
					value={account.name}
					onSave={onRename}
					action="?/renameAccount"
					id={account.id}
					href={`/accounts/${account.id}`}
				/>
			</div>
			<div class="flex items-center gap-2">
				{#await itemState.totals}
					<Skeleton class="h-8 w-24 rounded-full bg-background p-2" />
				{:then totals}
					<div class="flex items-center gap-2">
						{#if isSyncing}
							<Tooltip.Provider>
								<Tooltip.Root>
									<Tooltip.Trigger
										class={buttonVariants({ variant: 'ghost', size: 'icon' })}
										aria-label="Syncing positions"
										disabled
									>
										<RefreshCw class="h-4 w-4 animate-spin" />
									</Tooltip.Trigger>
									<Tooltip.Content>
										<p>Syncing positions...</p>
									</Tooltip.Content>
								</Tooltip.Root>
							</Tooltip.Provider>
						{:else}
							<Tooltip.Provider>
								<Tooltip.Root>
									<Tooltip.Trigger
										class={buttonVariants({ variant: 'ghost', size: 'icon' })}
										aria-label={account.api_sync_enabled ? 'Sync positions' : 'Update from CSV'}
										onclick={() => {
											if (account.api_sync_enabled) {
												onSync?.();
											} else {
												csvModalState.open();
											}
										}}
									>
										<RefreshCw class="h-4 w-4" />
									</Tooltip.Trigger>
									<Tooltip.Content>
										<p>{account.api_sync_enabled ? 'Sync positions' : 'Update from CSV'}</p>
									</Tooltip.Content>
								</Tooltip.Root>
							</Tooltip.Provider>
						{/if}
						<Tooltip.Provider>
							<Tooltip.Root>
								<Tooltip.Trigger class={buttonVariants({ variant: 'outline' })}>
									{money(totals.value)}
								</Tooltip.Trigger>
								<Tooltip.Content>
									<p>Total value: {money(totals.value)}</p>
									<p>Total cost: {money(totals.cost)}</p>
								</Tooltip.Content>
							</Tooltip.Root>
						</Tooltip.Provider>
					</div>
				{:catch}
					<div class="text-sm">Total: failed to load</div>
				{/await}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Button {...props} variant="ghost" size="icon" aria-label="Account actions">
								<EllipsisVertical class="h-4 w-4" />
							</Button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content>
						<DropdownMenu.Item
							variant="destructive"
							onSelect={() => {
								showDeleteModal = true;
							}}
						>
							Delete account
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		</div>
		<div class="flex items-center justify-between text-sm text-muted-foreground">
			<div class="flex flex-wrap items-center gap-x-2">
				<span>{getAccountTypeLabel(account.account_type_id)}</span>
				<span>•</span>
				<Badge
					variant="outline"
					class="border-muted-foreground/30 px-1.5 py-0 text-[10px] font-medium text-muted-foreground"
				>
					{account.currency}
				</Badge>
				<span>•</span>
				<span>
					{getInstitutionLabel(account.institution_id)}
					{#if account.broker_display_name}
						({account.broker_display_name})
					{/if}
				</span>
				<span>•</span>
				<span>{formatRelativeSyncTime(effectiveLastSyncAt)}</span>
			</div>
			{#if syncError}
				<span class="text-xs font-medium text-destructive">
					{syncError}
				</span>
			{/if}
		</div>

		{#if itemState.isExpanded}
			<div class="border-t border-border/50 pt-3">
				{#await itemState.holdingsPromise}
					<div class="space-y-2 py-2">
						<Skeleton class="h-8 w-full" />
						<Skeleton class="h-8 w-full" />
					</div>
				{:then holdings}
					<AccountInlineHoldings holdings={holdings ?? []} accountCurrency={account.currency} />
				{:catch}
					<div class="py-3 text-center text-sm text-destructive">
						Failed to load holdings. Please try again.
					</div>
				{/await}
			</div>
		{/if}
	</div>
</div>

<ConfirmationModal
	bind:open={showDeleteModal}
	title="Delete account"
	description={`Are you sure you want to delete "${account.name}"? This action cannot be undone.`}
	onconfirm={() => onDelete?.()}
/>

<UpdateAccountCsvModal
	{account}
	modalState={csvModalState}
	onSuccess={() => {
		itemState.invalidateCache(account.id);
		onAccountUpdated?.();
	}}
/>
