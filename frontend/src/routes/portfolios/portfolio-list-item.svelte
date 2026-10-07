<script lang="ts">
	import { browser } from '$app/environment';
	import type { Portfolio } from '$lib/types/portfolio';
	import EditableTitle from '$lib/components/forms/editable-title.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Skeleton from '$lib/components/ui/skeleton/skeleton.svelte';
	import TotalProfitLossButtons from '$lib/components/total-profit-loss-buttons.svelte';
	import { accountClient } from '$lib/api/accountClient';
	import {
		aggregateAccountTotals,
		type AccountTotalsInput,
		type CurrencyTotalsBucket
	} from '$lib/utils/finance/account-totals';
	import EllipsisVertical from '@lucide/svelte/icons/ellipsis-vertical';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { formatDate } from '$lib/utils/date';

	let {
		portfolio,
		onRename,
		onDelete
	}: {
		portfolio: Portfolio;
		onRename?: (newName: string) => void | Promise<void>;
		onDelete?: () => void | Promise<void>;
	} = $props();

	let isEditingTitle = $state(false);
	let showDeleteModal = $state(false);

	// Member-account server totals drive the card's value + P/L. A failed request
	// omits that account (same as the holdings header) instead of failing the row.
	async function loadTotals(): Promise<CurrencyTotalsBucket[]> {
		const accounts = portfolio.accounts ?? [];
		const results = await Promise.allSettled(
			accounts.map(async (account) => ({
				accountId: account.id,
				currency: account.currency,
				totals: await accountClient.getAccountTotals(account.id)
			}))
		);

		const inputs = results
			.filter(
				(result): result is PromiseFulfilledResult<AccountTotalsInput> =>
					result.status === 'fulfilled'
			)
			.map((result) => result.value);

		return aggregateAccountTotals(inputs);
	}

	const totalsPromise = $derived.by(() => {
		if (!browser) {
			return new Promise<CurrencyTotalsBucket[]>(() => {});
		}
		return loadTotals();
	});
</script>

<div
	class="portfolio-list-item flex space-x-4 rounded-lg bg-muted p-4"
	data-testid={`portfolio-item-${portfolio.id}`}
>
	<div class="flex-1 space-y-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-1">
				<EditableTitle
					value={portfolio.name}
					onSave={onRename}
					href={'/holdings?portfolio_id=' + portfolio.id}
					showEditButton={false}
					bind:isEditing={isEditingTitle}
					linkClass="rounded-md px-2 py-1 transition-colors hover:bg-background/60 dark:hover:bg-background/60 hover:no-underline font-semibold text-lg"
				/>
			</div>
			<div class="flex flex-wrap items-center justify-end gap-2">
				{#await totalsPromise}
					<Skeleton class="h-8 w-48 rounded-full bg-background p-2" />
				{:then totals}
					{#each totals as total (total.currency)}
						<TotalProfitLossButtons
							totalValue={total.totalValue}
							profitLoss={total.profitLoss}
							returnPercent={total.returnPercent}
							currency={total.currency}
							costBasis={total.basisAmount}
							basisLabel={total.basisLabel}
							testIdPrefix={`portfolio-${portfolio.id}-${total.currency}`}
						/>
					{/each}
				{/await}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Button
								{...props}
								variant="ghost"
								size="icon"
								class="rounded-md transition-colors hover:bg-background/60 dark:hover:bg-background/60"
								aria-label="Portfolio actions"
							>
								<EllipsisVertical class="h-4 w-4" />
							</Button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end">
						<DropdownMenu.Item
							onSelect={() => {
								isEditingTitle = true;
							}}
						>
							<Pencil class="h-4 w-4" />
							Rename
						</DropdownMenu.Item>
						<DropdownMenu.Item
							variant="destructive"
							onSelect={() => {
								showDeleteModal = true;
							}}
						>
							<Trash2 class="h-4 w-4" />
							Delete portfolio
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		</div>
		<div class="flex items-center text-sm text-muted-foreground">
			<div class="flex flex-wrap items-center gap-x-2">
				<span>
					{portfolio.accounts.length}
					{portfolio.accounts.length === 1 ? 'account' : 'accounts'}
				</span>
				{#if portfolio.created_at}
					<span>•</span>
					<span>Created {formatDate(portfolio.created_at)}</span>
				{/if}
			</div>
		</div>
	</div>
</div>

<ConfirmationModal
	bind:open={showDeleteModal}
	title="Delete portfolio"
	description={`Are you sure you want to delete "${portfolio.name}"? This action cannot be undone.`}
	onconfirm={() => onDelete?.()}
/>
