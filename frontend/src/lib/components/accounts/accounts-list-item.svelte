<script lang="ts">
	import { Institution } from '@/types/account';
	import Badge from '../ui/badge/badge.svelte';
	import EditableHeader from '../form/editable-header.svelte';
	import { accountService } from '@/services/accountService';
	import Skeleton from '../ui/skeleton/skeleton.svelte';
	import { money } from '@/types/money';
	import * as Tooltip from '../ui/tooltip';
	import { buttonVariants } from '../ui/button';

	let { account } = $props();

	let accountName = $state(account.name);
	let accountTotals = $derived.by(() => accountService.getAccountTotals(account.id));

	$effect(() => {
		accountName = account.name;
	});

	$effect(() => {
		if (accountName !== account.name) {
			accountService.renameAccount(account.id, accountName);
		}
	});
</script>

<div class="account-list-item group px flex space-x-4 rounded-lg bg-muted p-4">
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
