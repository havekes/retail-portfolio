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

	type GroupBy = 'none' | 'institution' | 'accountType';
	let groupBy: GroupBy = 'none';
	let accounts: Account[] = [];
	let isLoading = true;
	let error: string | null = null;

	const groupByLabels: Record<GroupBy, string> = {
		none: 'None',
		institution: 'Institution',
		accountType: 'Account type'
	};

	const accountTypeLabels: Record<AccountType, string> = {
		[AccountType.TFSA]: 'TFSA',
		[AccountType.RRSP]: 'RRSP',
		[AccountType.FHSA]: 'FHSA',
		[AccountType.NonRegistered]: 'Non-Registered'
	};

	const institutionLabels: Record<Institution, string> = {
		[Institution.Wealthsimple]: 'Wealthsimple'
	};

	const getInstitutionLabel = (id: Institution): string => institutionLabels[id] ?? 'Unknown';
	const getAccountTypeLabel = (id: AccountType): string => accountTypeLabels[id] ?? 'Unknown';

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

	$: groupedAccounts = groupAccounts(accounts, groupBy);

	onMount(async () => {
		try {
			accounts = await accountService.getAccounts();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load accounts';
		} finally {
			isLoading = false;
		}
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
		{#if isLoading}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:else if error}
			<div class="rounded-md bg-red-50 p-4 text-sm text-red-800">{error}</div>
		{:else if accounts.length === 0}
			<p class="text-center text-sm text-muted-foreground">No accounts found</p>
		{:else}
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
		{/if}
	</div>
</div>
