<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { AccountGroupKeys, type Account } from '@/types/account';
	import { onMount } from 'svelte';
	import { accountService } from '@/services/accountService';
	import { group, groupAccounts, type GroupBy } from '@/group';

	let accounts = $state<Promise<Set<Account>> | null>(new Set());
	let selectionMode = $state(false);
	let selectedAccounts = $state<string[]>([]);
	let isCreatePortfolioDisabled = $derived(selectionMode && selectedAccounts.length === 0);

	let groupBy = <GroupBy>'none';
	$: groupedAccounts = accounts ? groupAccounts(accounts, groupBy) : null;

	const groupByLabels: Record<GroupBy, string> = {
		none: 'None',
		institution: 'Institution',
		accountType: 'Account type'
	};
	let groupByKey = null;
	$: groupedAccounts = accounts ? group<Account, AccountGroupKeys>(accounts, groupByKey) : null;

	onMount(() => {
		accounts = accountService.getAccounts();
	});

	function toggleSelectionMode() {
		selectionMode = true;
	}

	function cancelSelection() {
		selectionMode = false;
		selectedAccounts = [];
	}

	function createPortfolio() {
		console.log(selectedAccounts);
		selectionMode = false;
		selectedAccounts = [];
	}

	function handleCreatePortfolioClick() {
		if (selectionMode) {
			createPortfolio();

			return;
		}

		toggleSelectionMode();
	}
</script>

<div class="accounts-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Accounts</h2>
		<div class="ms-auto">
			{#if selectionMode}
				<Button variant="outline" onclick={cancelSelection}>Cancel</Button>
			{/if}
			<Button disabled={isCreatePortfolioDisabled} onclick={handleCreatePortfolioClick}>
			    {selectionMode ? 'Confirm Selection' : 'Create portfolio'}
			</Button>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					<Button variant="outline">
						Group by: {groupByLabels[groupBy]}
						<ChevronDown />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content>
					<DropdownMenu.RadioGroup bind:value={groupBy}>
						<DropdownMenu.RadioItem value="none">{groupByLabels.none}</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="institution">
							{groupByLabels.institution}
						</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="accountType">
							{groupByLabels.accountType}
						</DropdownMenu.RadioItem>
					</DropdownMenu.RadioGroup>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</div>

	<div class="space-y-4 px-4">
		{#await accounts}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:then}
			{#await groupedAccounts}
				<Skeleton class="h-16 w-full rounded-md" />
				<Skeleton class="h-16 w-full rounded-md" />
				<Skeleton class="h-16 w-full rounded-md" />
			{:then groups}
				{#each groups as group (group.key)}
					<div class="space-y-3">
						{#if groupBy !== 'none'}
							<h3 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
								{group.label}
								<!-- Call method to compute label using key value -->
							</h3>
						{/if}
						{#each group.accounts as account (account.id)}
		                       <AccountsListItem {account} {selectionMode} bind:selectedAccounts />
						{/each}
					</div>
				{/each}
			{:catch error}
				<div class="error">Error: {error.message}</div>
			{/await}
		{:catch error}
			<div class="error">Error: {error.message}</div>
		{/await}
	</div>
</div>
