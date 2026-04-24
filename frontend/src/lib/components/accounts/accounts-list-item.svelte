<script lang="ts">
	import { getAccountTypeLabel, getInstitutionLabel } from '@/types/account';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import EditableTitle from '../forms/editable-title.svelte';
	import Skeleton from '../ui/skeleton/skeleton.svelte';
	import { money } from '@/types/money';
	import * as Tooltip from '../ui/tooltip';
	import { buttonVariants } from '../ui/button';
	import { AccountsListItemState } from './accounts-list-item.svelte.js';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';

	let { account, selectionMode, isSelected, onToggleSelection, isSyncing, onSync, syncError } =
		$props();

	const state = new AccountsListItemState(() => account.id);

	$effect(() => {
		if (!isSyncing) {
			state.invalidateCache(account.id);
		}
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
		<div class="flex justify-between">
			<EditableTitle
				bind:value={account.name}
				action="?/renameAccount"
				id={account.id}
				href={`/accounts/${account.id}`}
			/>
			<div>
				{#await state.totals}
					<Skeleton class="h-8 w-24 rounded-full bg-background p-2" />
				{:then totals}
					<div class="flex items-center gap-2">
						{#if isSyncing}
							<Tooltip.Provider>
								<Tooltip.Root>
									<Tooltip.Trigger
										class={buttonVariants({ variant: 'ghost', size: 'icon' })}
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
										onclick={onSync}
									>
										<RefreshCw class="h-4 w-4" />
									</Tooltip.Trigger>
									<Tooltip.Content>
										<p>Sync positions</p>
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
			</div>
		</div>
		<div class="flex items-center justify-between text-sm text-muted-foreground">
			<div class="flex items-center gap-x-2">
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
			</div>
			{#if syncError}
				<span class="text-xs font-medium text-destructive">
					{syncError}
				</span>
			{/if}
		</div>
	</div>
</div>
