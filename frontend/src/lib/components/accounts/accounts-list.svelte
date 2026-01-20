<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import type { Account } from '@/types/account';
	import { AccountType, Institution } from '@/types/account';
	import { onMount } from 'svelte';
	import { accountService } from '@/services/accountService';

	let accounts: Promise<Array<Account>> | null = null;
	type GroupBy = 'none' | 'institution' | 'accountType';
	let groupBy: GroupBy = 'none';

	const groupByLabels: Record<GroupBy, string> = {
		none: 'None',
		institution: 'Institution',
		accountType: 'Account type'
	};

	const getInstitutionLabel = (id: Institution): string => Institution[id] ?? 'Unknown';
	const getAccountTypeLabel = (id: AccountType): string => AccountType[id] ?? 'Unknown';

	const groupAccounts = (items: Account[], group: GroupBy) => {
		if (group === 'none') {
			return [{ key: 'all', label: '', accounts: items }];
		}

		const groups: Record<string, { key: string; label: string; accounts: Account[] }> = {};
		for (const account of items) {
			const key =
				group === 'institution' ? String(account.institution_id) : String(account.account_type_id);
			const label =
				group === 'institution'
					? getInstitutionLabel(account.institution_id)
					: getAccountTypeLabel(account.account_type_id);
			const existing = groups[key];
			if (existing) {
				existing.accounts.push(account);
			} else {
				groups[key] = { key, label, accounts: [account] };
			}
		}

		return Object.values(groups);
	};

	let groupedAccounts: ReturnType<typeof groupAccounts> = [];
	let resolvedAccounts: Account[] = [];

	$: if (accounts) {
		accounts.then((data) => {
			resolvedAccounts = data;
		});
	}

	$: groupedAccounts = groupAccounts(resolvedAccounts, groupBy);

	onMount(() => {
		accounts = accountService.getAccounts();
	});
</script>

<div class="accounts-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Accounts</h2>
		<div class="ms-auto">
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					<Button variant="outline">
						Group by: {groupByLabels[groupBy]}
						<ChevronDown />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content>
					<DropdownMenu.RadioGroup bind:value={groupBy}>
						<DropdownMenu.RadioItem value="none">None</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="institution">Institution</DropdownMenu.RadioItem>
						<DropdownMenu.RadioItem value="accountType">Account type</DropdownMenu.RadioItem>
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
			{#each groupedAccounts as group (group.key)}
				<div class="space-y-3">
					{#if groupBy !== 'none'}
						<h3 class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
							{group.label}
						</h3>
					{/if}
					{#each group.accounts as account (account.id)}
						<AccountsListItem {account} />
					{/each}
				</div>
			{/each}
		{:catch error}
			<div class="error">Error: {error.message}</div>
		{/await}
	</div>
</div>
