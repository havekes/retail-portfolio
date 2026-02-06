<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import {
		type AccountGroupKeys,
		type Account,
		getAccountTypeLabel,
		getInstitutionLabel
	} from '@/types/account';
	import { onMount } from 'svelte';
	import { accountService } from '@/services/accountService';
	import { group } from '@/group';

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
	let accounts = <Promise<Array<Account>> | null>null;
	let groupByKey: AccountGroupKeys | null = null;
	$: groupedAccountsMap = accounts ? group<Account, AccountGroupKeys>(accounts, groupByKey) : null;
	$: groupedAccounts = groupedAccountsMap
		? (async () => {
				const map = await groupedAccountsMap;
				return Array.from(map.entries()).map(([key, items]) => ({
					key: key ?? 'none',
					label: getGroupLabel(groupByKey, key),
					accounts: items
				}));
			})()
		: null;

	const groupByLabels: Record<string, string> = {
		none: 'None',
		institution_id: 'Institution',
		account_type_id: 'Account Type'
	};

	const getGroupLabel = (groupKey: AccountGroupKeys | null, value: string | number): string => {
		if (groupKey === null || value === null) {
			return '';
		}

		if (groupKey === 'institution_id') {
			return getInstitutionLabel(value);
		} else if (groupKey === 'account_type_id') {
			return getAccountTypeLabel(value);
		}

		return String(value);
	};

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
						Group by: {groupByLabels[groupByKey ?? 'none']}
						<ChevronDown />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content>
					<DropdownMenu.RadioGroup bind:value={groupByKey}>
						<DropdownMenu.RadioItem value={null}>{groupByLabels.none}</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="institution_id">
							{groupByLabels.institution_id}
						</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="account_type_id">
							{groupByLabels.account_type_id}
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
				{#each groups as groupItem (groupItem.key)}
					<div class="space-y-3">
						{#if groupByKey !== null}
							<h3 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
								{groupItem.label}
							</h3>
						{/if}
						{#each groupItem.accounts as account (account.id)}
							<AccountsListItem {account} />
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
