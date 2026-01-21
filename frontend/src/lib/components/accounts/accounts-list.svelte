<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { AccountType, Institution } from '@/types/account';
	import { groupAccounts } from '@/utils/group';
	import { accountService } from '@/services/accountService';

	type GroupBy = 'none' | 'institution' | 'accountType';
	let groupBy: GroupBy = 'none';
	let accountsPromise = accountService.getAccounts();

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

	const getLabelMap = () => groupBy === 'institution' ? institutionLabels : accountTypeLabels;
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
		{#await accountsPromise}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:catch error}
			<div class="rounded-md bg-red-50 p-4 text-sm text-red-800">
				{error instanceof Error ? error.message : 'Failed to load accounts'}
			</div>
		{:then accounts}
			{#if accounts.length === 0}
				<p class="text-center text-sm text-muted-foreground">No accounts found</p>
			{:else}
				{@const labelMap = getLabelMap()}
				{@const grouped = accounts.length > 0 ? groupAccounts(Promise.resolve(accounts), groupBy, labelMap) : Promise.resolve([])}
				{#await grouped then groups}
					{#each groups as group (group.key)}
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
				{/await}
			{/if}
		{/await}
	</div>
</div>
