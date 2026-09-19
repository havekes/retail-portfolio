<script lang="ts">
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import HoldingsTable from '$lib/components/holdings/holdings-table.svelte';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import Settings2 from '@lucide/svelte/icons/settings-2';
	import { HoldingsService } from '$lib/components/holdings/holdingsService.svelte';
	import { saveHoldingsTableConfig } from '$lib/components/holdings/holdings-table-prefs';
	import { saveHoldingsGroupMode } from '$lib/components/holdings/holdings-group-prefs';
	import { getUserPreferencesService } from '$lib/api/userPreferencesService';
	import { SvelteMap } from 'svelte/reactivity';
	import { cn } from '$lib/utils';
	import {
		HOLDINGS_TABLE_COLUMNS,
		HOLDINGS_TABLE_STICKY_COLUMN_ID,
		normalizeHoldingsTableConfig,
		toggleColumnVisibility,
		type HoldingsTableColumnId,
		type HoldingsTableConfig
	} from '$lib/components/holdings/holdings-table-columns';
	import type { HoldingsGroupMode } from '$lib/utils/finance/holdings-group';

	let { data } = $props();

	// The page owns its service instance (SSR "no global instances" rule) and seeds
	// it from the server load: toggling grouping never triggers a refetch.
	const service = new HoldingsService();
	service.rows = data.holdings;
	service.setGroupBy(data.group_mode);

	const prefsService = getUserPreferencesService();

	let tableConfig = $state<HoldingsTableConfig>(
		normalizeHoldingsTableConfig(data.holdings_table_config)
	);

	let persistError = $state<string | null>(null);
	const errorMessage = $derived(persistError ?? service.errorMessage);

	// Never sum across currencies: the backend converts each row into its account's
	// currency, so totals are bucketed per currency.
	const currencyTotals = $derived.by(() => {
		const buckets = new SvelteMap<
			string,
			{
				currency: string;
				totalValue: number;
				profitLoss: number;
				costBasis: number;
				hasProfitLoss: boolean;
			}
		>();

		for (const row of service.rows) {
			let bucket = buckets.get(row.currency);
			if (!bucket) {
				bucket = {
					currency: row.currency,
					totalValue: 0,
					profitLoss: 0,
					costBasis: 0,
					hasProfitLoss: false
				};
				buckets.set(row.currency, bucket);
			}

			bucket.totalValue += row.total_value;
			if (row.profit_loss !== null && row.profit_loss !== undefined) {
				bucket.profitLoss += row.profit_loss;
				bucket.hasProfitLoss = true;
			}
			const rowCostBasis = row.quantity * (row.converted_average_cost ?? row.average_cost ?? 0);
			if (rowCostBasis > 0) {
				bucket.costBasis += rowCostBasis;
			}
		}

		return [...buckets.values()].map((bucket) => ({
			...bucket,
			returnPercent: bucket.costBasis > 0 ? (bucket.profitLoss / bucket.costBasis) * 100 : null
		}));
	});

	function persist(promise: Promise<void>, fallbackMessage: string) {
		persistError = null;
		promise.catch((err) => {
			persistError = err instanceof Error ? err.message : fallbackMessage;
		});
	}

	function handleGroupToggle(checked: boolean | 'indeterminate') {
		const mode: HoldingsGroupMode = checked === true ? 'stock' : 'none';
		service.setGroupBy(mode);
		persist(saveHoldingsGroupMode(prefsService, mode), 'Failed to save group preference');
	}

	function handleToggleColumn(columnId: HoldingsTableColumnId) {
		const nextConfig = toggleColumnVisibility(tableConfig, columnId);
		tableConfig = nextConfig;
		persist(saveHoldingsTableConfig(prefsService, nextConfig), 'Failed to save column preferences');
	}

	function handleConfigChange(nextConfig: HoldingsTableConfig) {
		tableConfig = nextConfig;
		persist(saveHoldingsTableConfig(prefsService, nextConfig), 'Failed to save column preferences');
	}

	const formatCurrency = (amount: number, currency: string) =>
		new Intl.NumberFormat('en-CA', { style: 'currency', currency }).format(amount);

	function getPillClass(changePercent: number | null | undefined): string {
		if (changePercent == null || Number.isNaN(Number(changePercent))) {
			return 'text-muted-foreground bg-muted/40 border-border/40';
		}
		const num = Number(changePercent);
		if (num > 0) {
			return 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
		}
		if (num < 0) {
			return 'text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20';
		}
		return 'text-muted-foreground bg-muted/40 border-border/40';
	}

	const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
</script>

<svelte:head>
	<title>Holdings</title>
</svelte:head>

<div class="flex h-full flex-col overflow-hidden bg-background">
	<PageHeader title="Holdings" subtitle="All holdings across your accounts">
		{#snippet actions()}
			<div class="flex items-center gap-6">
				{#each currencyTotals as total (total.currency)}
					<div class="flex items-center gap-3" data-testid={`currency-total-${total.currency}`}>
						<div class="flex flex-col items-end leading-tight">
							<span class="text-[10px] tracking-tight text-muted-foreground uppercase">
								{total.currency} TOTAL
							</span>
							<span class="text-base font-semibold text-foreground tabular-nums">
								{formatCurrency(total.totalValue, total.currency)}
							</span>
						</div>
						{#if total.hasProfitLoss}
							<div class="flex flex-col items-end gap-0.5 leading-tight">
								{#if total.returnPercent !== null}
									<span
										data-testid={`currency-return-percent-${total.currency}`}
										class={cn(
											'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
											getPillClass(total.returnPercent)
										)}
									>
										{formatPercent(total.returnPercent)}
									</span>
								{/if}
								<span
									data-testid={`currency-profit-loss-${total.currency}`}
									class="text-xs text-muted-foreground tabular-nums"
								>
									{total.profitLoss >= 0 ? '+' : ''}{formatCurrency(
										total.profitLoss,
										total.currency
									)}
								</span>
							</div>
						{/if}
					</div>
				{/each}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<button
								{...props}
								type="button"
								data-testid="display-settings-trigger"
								aria-label="Display settings"
								title="Display settings"
								class="inline-flex size-8 items-center justify-center rounded-md border border-input bg-background text-muted-foreground shadow-xs transition-colors hover:bg-accent hover:text-accent-foreground"
							>
								<Settings2 size={16} />
							</button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end" class="w-48">
						<DropdownMenu.Label>View options</DropdownMenu.Label>
						<DropdownMenu.CheckboxItem
							data-testid="group-by-stock"
							checked={service.groupBy === 'stock' || service.groupBy === 'company'}
							onCheckedChange={handleGroupToggle}
						>
							Group by stock
						</DropdownMenu.CheckboxItem>
						<DropdownMenu.Separator />
						<DropdownMenu.Label>Visible columns</DropdownMenu.Label>
						<DropdownMenu.Separator />
						{#each HOLDINGS_TABLE_COLUMNS as column (column.id)}
							<DropdownMenu.CheckboxItem
								checked={tableConfig.visible.includes(column.id)}
								disabled={column.id === HOLDINGS_TABLE_STICKY_COLUMN_ID}
								onCheckedChange={() => handleToggleColumn(column.id)}
								data-testid={`column-toggle-${column.id}`}
							>
								{column.label}
							</DropdownMenu.CheckboxItem>
						{/each}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		{/snippet}
	</PageHeader>

	{#if errorMessage}
		<div class="px-4 pt-3">
			<Alert.Root variant="destructive" data-testid="holdings-error">
				<Alert.Description>{errorMessage}</Alert.Description>
			</Alert.Root>
		</div>
	{/if}

	<main class="flex-1 overflow-auto">
		<HoldingsTable
			holdings={service.rows}
			groupBy={service.groupBy === 'stock' || service.groupBy === 'company' ? 'stock' : null}
			isLoading={service.isLoading}
			{tableConfig}
			onConfigChange={handleConfigChange}
			elliottWaves={data.elliott_waves}
			emptyMessage="No holdings yet. Import an account to see your holdings here."
		/>
	</main>
</div>
