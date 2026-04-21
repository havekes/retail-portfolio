<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { onMount } from 'svelte';
	import { AccountsListState } from './accounts-list.svelte.js';

	const state = new AccountsListState();

	onMount(() => {
		state.fetchAccounts();

		return () => state.destroy();
	});

	$effect(() => {
		console.log('Syncing account IDs updated:', Array.from(state.syncingAccountIds));
	});
</script>

<div class="accounts-list w-full space-y-4">
	<div class="flex h-[49px] items-center border-b px-4 py-2">
		<h2>Accounts</h2>
		<div class="ms-4 flex items-center gap-2 text-xs">
			<div class="h-2 w-2 rounded-full {state.wsConnected ? 'bg-green-500' : 'bg-red-500'}"></div>
			<span class="text-muted-foreground">{state.wsConnected ? 'Live' : 'Disconnected'}</span>
		</div>
		<div class="ms-auto flex items-center gap-2">
			{#if state.selectionMode}
				<Button variant="outline" onclick={() => state.cancelSelection()}>Cancel</Button>
			{/if}
			<Button
				disabled={state.isCreatePortfolioDisabled}
				onclick={() => state.handleCreatePortfolioClick()}
			>
				{state.selectionMode ? 'Confirm Selection' : 'Create portfolio'}
			</Button>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Button {...props} variant="outline">
							Group by: {state.groupByLabels[state.groupBy]}
							<ChevronDown />
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content>
					<DropdownMenu.RadioGroup bind:value={state.groupBy}>
						<DropdownMenu.RadioItem value="none">
							{state.groupByLabels.none}
						</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="institution">
							{state.groupByLabels.institution}
						</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="accountType">
							{state.groupByLabels.accountType}
						</DropdownMenu.RadioItem>
					</DropdownMenu.RadioGroup>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</div>

	<div class="space-y-4 px-4">
		{#if state.isLoading && state.accounts.length === 0}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:else}
			{#await state.groupedAccounts}
				<Skeleton class="h-16 w-full rounded-md" />
				<Skeleton class="h-16 w-full rounded-md" />
				<Skeleton class="h-16 w-full rounded-md" />
			{:then groups}
				{#each groups as group (group.key)}
					<div class="space-y-3">
						{#if state.groupBy !== 'none'}
							<h3 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
								{group.label}
							</h3>
						{/if}
						{#each group.accounts as account (account.id)}
							<AccountsListItem
								{account}
								selectionMode={state.selectionMode}
								isSelected={state.selectedAccounts.includes(account.id)}
								isSyncing={state.syncingAccountIds.has(account.id)}
								syncError={state.syncErrors[account.id]}
								onToggleSelection={() => state.toggleAccountSelection(account.id)}
								onSync={() => state.syncAccount(account.id)}
							/>
						{/each}
					</div>
				{/each}
			{:catch error}
				<div class="error text-destructive">Error: {error.message}</div>
			{/await}
		{/if}
	</div>
</div>
