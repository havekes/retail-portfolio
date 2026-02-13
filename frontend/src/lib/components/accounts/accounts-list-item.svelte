<script lang="ts">
	import { Institution } from '@/types/account';
	import Badge from '../ui/badge/badge.svelte';
	import Checkbox from '../ui/checkbox/checkbox.svelte';
	import EditableHeader from '../form/editable-header.svelte';
	import { accountService } from '@/services/accountService';
	import Skeleton from '../ui/skeleton/skeleton.svelte';
	import { money } from '@/types/money';
	import * as Tooltip from '../ui/tooltip';
	import { buttonVariants } from '../ui/button';

	let { account, selectionMode, selectedAccounts = $bindable() } = $props();

	let accountName = $state(account.name);
	let accountTotals = accountService.getAccountTotals(account.id);

	$effect(() => {
		if (accountName !== account.name) {
			accountService.renameAccount(account.id, accountName);
		}
	});

	function toggleSelection() {
		if (selectedAccounts.includes(account.id)) {
			selectedAccounts = selectedAccounts.filter((id) => id !== account.id);

			return;
		}

		selectedAccounts = [...selectedAccounts, account.id];
	}
</script>

<div class="account-list-item group px flex space-x-4 rounded-lg bg-muted p-4">
	{#if selectionMode}
		<div class="flex border-r py-2 pr-4">
			<div class="m-auto">
				<Checkbox
					class="cursor-pointer"
					checked={selectedAccounts.includes(account.id)}
					onCheckedChange={toggleSelection}
				/>
			</div>
		</div>
	{/if}

	<div class="flex-1 space-y-2">
		<EditableHeader bind:value={accountName} />
		<div class="flex gap-x-2 text-sm">
			<Badge variant="outline">{account.currency}</Badge>
			<span>{Institution[account.institution_id]}</span>
		</div>
	</div>
	<div>
		{#await accountTotals}
			<Skeleton class="h-8 w-24 rounded-full bg-background p-2" />
		{:then totals}
			<Tooltip.Provider>
				<Tooltip.Root>
					<Tooltip.Trigger class={buttonVariants({ variant: 'outline' })}>
						{money(totals.cost)}
					</Tooltip.Trigger>
					<Tooltip.Content>
						<p>Total cost</p>
					</Tooltip.Content>
				</Tooltip.Root>
			</Tooltip.Provider>
		{:catch}
			<div class="text-sm">Total: failed to load</div>
		{/await}
	</div>
</div>
