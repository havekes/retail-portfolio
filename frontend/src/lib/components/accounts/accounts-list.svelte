<script lang="ts">
	import AccountsListItem from './accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import * as DropdownMenu from '../ui/dropdown-menu';
	import Button from '../ui/button/button.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import type { Account } from '@/types/account';
	import { onMount } from 'svelte';
	import { accountService } from '@/services/accountService';

	let accounts = $state<Promise<Set<Account>> | null>(new Set());
	let selectionMode = $state(false);
	let selectedAccounts = $state<string[]>([]);
	let isCreatePortfolioDisabled = $derived(selectionMode && selectedAccounts.length === 0);

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
				<AccountsListItem {account} {selectionMode} bind:selectedAccounts />
			{/each}
		{:catch error}
			<div class="error">Error: {error.message}</div>
		{/await}
	</div>
</div>
