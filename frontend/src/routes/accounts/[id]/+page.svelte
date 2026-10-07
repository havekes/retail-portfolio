<script lang="ts">
	import PageHeader from '@/components/layout/app-header.svelte';
	import HoldingsTable from '@/components/accounts/holdings-table.svelte';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import EditableTitle from '@/components/forms/editable-title.svelte';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';

	let { data } = $props();

	const formatCurrency = (amount: number, currency: string) => {
		return new Intl.NumberFormat('en-CA', {
			style: 'currency',
			currency: currency
		}).format(amount);
	};
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
			<div class="flex items-center gap-6">
				<div class="flex flex-col items-end">
					<span class="text-[10px] tracking-tight text-muted-foreground uppercase">Total Value</span
					>
					<span class="text-base font-semibold text-foreground tabular-nums">
						{formatCurrency(data.holdings.total_value, data.holdings.currency)}
					</span>
				</div>
				<div class="flex flex-col items-end">
					<span class="text-[10px] tracking-tight text-muted-foreground uppercase"
						>Net Deposits</span
					>
					<span class="text-base font-semibold text-foreground/80 tabular-nums">
						{data.holdings.net_deposits !== null
							? formatCurrency(data.holdings.net_deposits, data.holdings.currency)
							: '—'}
					</span>
				</div>
				<div class="flex flex-col items-end">
					<span class="text-[10px] tracking-tight text-muted-foreground uppercase">Total P/L</span>
					<span
						class={`text-base font-semibold tabular-nums ${data.holdings.total_profit_loss >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
					>
						{data.holdings.total_profit_loss >= 0 ? '+' : ''}{formatCurrency(
							data.holdings.total_profit_loss,
							data.holdings.currency
						)}
						{#if data.holdings.total_profit_loss_percent !== null}
							<span class="ml-1 text-sm font-medium">
								({data.holdings.total_profit_loss_percent >= 0
									? '+'
									: ''}{data.holdings.total_profit_loss_percent.toFixed(2)}%)
							</span>
						{/if}
					</span>
				</div>
			</div>
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
