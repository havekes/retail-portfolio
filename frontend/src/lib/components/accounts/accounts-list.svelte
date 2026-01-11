<script lang="ts">
	import { accountService } from '@/services/accountService';
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	let accounts = accountService.getAccounts();
</script>

<div class="accounts-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Accounts</h2>
		<div class="ms-auto">
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					<Button variant="outline">
						Group by
						<ChevronDown />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content>
					<DropdownMenu.Item>None</DropdownMenu.Item>
					<DropdownMenu.Item>Institution</DropdownMenu.Item>
					<DropdownMenu.Item>Account type</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</div>

	<div class="space-y-4 px-4">
		{#await accounts}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:then accounts}
			{#each accounts as account (account.id)}
				<AccountsListItem {account} />
			{/each}
		{:catch error}
			<div class="error">Error: {error.message}</div>
		{/await}
	</div>
</div>
