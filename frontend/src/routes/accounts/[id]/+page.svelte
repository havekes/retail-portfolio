<script lang="ts">
	import AppSidebar from '@/components/layout/app-sidebar.svelte';
	import PageHeader from '@/components/layout/app-header.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import HoldingsTable from '@/components/accounts/holdings-table.svelte';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import EditableTitle from '@/components/forms/editable-title.svelte';
	import { accountClient } from '$lib/api/accountClient';

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

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset>
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
					</div>
				{/snippet}

				{#snippet actions()}
					<div class="flex items-center gap-6">
						<div class="flex flex-col items-end">
							<span class="text-[10px] tracking-tight text-muted-foreground uppercase"
								>Total Value</span
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
							<span class="text-[10px] tracking-tight text-muted-foreground uppercase"
								>Total P/L</span
							>
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
				<div class="animate-in duration-500 fade-in">
					<HoldingsTable
						holdings={data.holdings.holdings}
						totalAccountValue={data.holdings.total_value}
					/>
				</div>
			</main>
		</div>
	</Sidebar.Inset>
</Sidebar.Provider>

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
