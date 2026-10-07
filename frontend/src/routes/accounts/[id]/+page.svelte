<script lang="ts">
	import PageHeader from '@/components/layout/app-header.svelte';
	import HoldingsTable from '@/components/accounts/holdings-table.svelte';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import EditableTitle from '@/components/forms/editable-title.svelte';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import TotalProfitLossButtons from '$lib/components/total-profit-loss-buttons.svelte';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { data } = $props();
</script>

<svelte:head>
	<title>{data.holdings.account_name} - Account Details</title>
</svelte:head>

<div class="flex flex-1 flex-col overflow-hidden bg-background">
	<PageHeader subtitle="Account Holdings">
		{#snippet titleSlot()}
			<div class="flex items-center gap-3">
				<EditableTitle
					bind:value={data.holdings.account_name}
					action="?/renameAccount"
					id={data.holdings.account_id}
					textClass="text-lg font-semibold"
				/>
				<Badge
					variant="outline"
					class="border-muted-foreground/30 px-1.5 py-0 text-[10px] font-medium text-muted-foreground"
				>
					{data.holdings.currency}
				</Badge>
				{#if data.holdings.pricing_incomplete}
					<Tooltip.Provider>
						<Tooltip.Root>
							<Tooltip.Trigger
								class="rounded-md p-1 text-amber-600 transition-colors hover:bg-background/60 dark:hover:bg-background/60"
								aria-label="Incomplete pricing"
							>
								<TriangleAlert class="h-4 w-4" />
							</Tooltip.Trigger>
							<Tooltip.Content>
								<p>Some positions are missing prices. They are excluded from these totals.</p>
							</Tooltip.Content>
						</Tooltip.Root>
					</Tooltip.Provider>
				{/if}
			</div>
		{/snippet}

		{#snippet actions()}
			<TotalProfitLossButtons
				totalValue={data.holdings.total_value}
				profitLoss={data.holdings.total_profit_loss}
				returnPercent={data.holdings.total_profit_loss_percent}
				currency={data.holdings.currency}
				costBasis={data.holdings.net_deposits}
				basisLabel={data.holdings.profit_loss_basis === 'cost' ? 'Cost basis' : 'Net deposits'}
			/>
		{/snippet}
	</PageHeader>

	<main class="flex-1 overflow-y-auto">
		{#if data.holdings && data.holdings.items.length > 0}
			<HoldingsTable holdings={data.holdings.items} totalAccountValue={data.holdings.total_value} />
		{/if}
	</main>
</div>

<style>
	:global(.animate-in) {
		animation: enter 0.4s ease-out forwards;
	}

	@keyframes enter {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
