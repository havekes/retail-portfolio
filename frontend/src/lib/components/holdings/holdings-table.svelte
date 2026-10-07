<script lang="ts">
	import { resolve } from '$app/paths';
	import { SvelteMap } from 'svelte/reactivity';
	import type { UserHolding } from '$lib/types/account';
	import {
		getLatestWaveCount,
		getWaveTargetPrice,
		calculateUpsidePercentage,
		type SecurityElliottWaves
	} from '$lib/utils/finance/elliott-wave';
	import { groupHoldings } from '$lib/utils/finance/holdings-group';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { cn } from '$lib/utils';
	import type { SecurityValuation } from '$lib/api/marketService';
	import { formatValuationRange } from '$lib/utils/finance/valuation';
	import { formatDate } from '$lib/utils/date';
	import {
		calculatePercentOfTotal,
		calculatePercentOfAccount,
		formatHoldingPercent
	} from '$lib/utils/finance/holdings-metrics';
	import {
		HOLDINGS_TABLE_COLUMNS,
		HOLDINGS_TABLE_STICKY_COLUMN_ID,
		clampColumnWidth,
		normalizeHoldingsTableConfig,
		type HoldingsTableColumnId,
		type HoldingsTableColumn,
		type HoldingsTableConfig
	} from './holdings-table-columns';
	import ValuationModal from '$lib/components/actions-sidebar/fundamentals/valuation-modal.svelte';
	import { ModalState } from '$lib/utils/modal-state.svelte';
	import type { SecurityValuationRead } from '$lib/api/valuationClient';

	type Props = {
		holdings: UserHolding[];
		groupBy?: 'stock' | 'company' | null;
		isLoading?: boolean;
		emptyMessage?: string;
		tableConfig?: HoldingsTableConfig | null;
		onConfigChange?: (config: HoldingsTableConfig) => void;
		onAccountClick?: (accountId: string) => void;
		onValuationChange?: (securityId: string, valuation: SecurityValuationRead) => void;
		elliottWaves?: Record<string, SecurityElliottWaves> | null;
		valuations?: Record<string, SecurityValuation> | null;
	};

	let {
		holdings,
		groupBy = null,
		isLoading = false,
		emptyMessage = 'No holdings yet.',
		tableConfig = null,
		onConfigChange,
		onAccountClick,
		onValuationChange,
		elliottWaves = null,
		valuations = null
	}: Props = $props();

	const valuationModalState = new ModalState<{
		securityId: string;
		valuation?: SecurityValuationRead | null;
	}>();

	function handleValuationClick(row: HoldingRowView) {
		const currentVal = valuations?.[row.security_id];
		valuationModalState.open({
			securityId: row.security_id,
			valuation: currentVal
				? {
						id: currentVal.id ?? 0,
						user_id: currentVal.user_id ?? '',
						security_id: row.security_id,
						lower_bound: currentVal.lower_bound,
						upper_bound: currentVal.upper_bound,
						created_at: currentVal.created_at ?? '',
						updated_at: currentVal.updated_at ?? ''
					}
				: null
		});
	}

	// Writable derived: normalizes the consumer's config, but a drag can
	// override it locally for immediate feedback until the prop changes again.
	// The consumer owns persistence via `onConfigChange`.
	let config = $derived(normalizeHoldingsTableConfig(tableConfig));

	const visibleColumns = $derived(
		HOLDINGS_TABLE_COLUMNS.filter((column) => config.visible.includes(column.id))
	);
	const visibleColumnCount = $derived(visibleColumns.length);
	const isVisible = (id: HoldingsTableColumnId) => config.visible.includes(id);

	const SKELETON_ROWS = 5;
	const SKELETON_ROW_INDEXES = [...Array(SKELETON_ROWS).keys()];

	let sortColumn = $state<HoldingsTableColumnId>('total_value');
	let sortDirection = $state<'asc' | 'desc'>('desc');

	type Resize = { column: HoldingsTableColumnId; startX: number; startWidth: number };
	let resize = $state<Resize | null>(null);

	function handleResizePointerDown(event: PointerEvent, column: HoldingsTableColumnId) {
		event.preventDefault();
		event.stopPropagation();
		resize = { column, startX: event.clientX, startWidth: config.widths[column] };
		const target = event.currentTarget as HTMLElement;
		if (typeof target.setPointerCapture === 'function') {
			try {
				target.setPointerCapture(event.pointerId);
			} catch {
				// jsdom has no pointer capture — the handlers still receive the events.
			}
		}
	}

	function handleResizePointerMove(event: PointerEvent) {
		if (!resize) return;
		const nextWidth = clampColumnWidth(
			resize.column,
			resize.startWidth + (event.clientX - resize.startX)
		);
		if (nextWidth === config.widths[resize.column]) return;
		config = { ...config, widths: { ...config.widths, [resize.column]: nextWidth } };
	}

	function handleResizePointerUp(event: PointerEvent) {
		if (!resize) return;
		const target = event.currentTarget as HTMLElement;
		if (typeof target.releasePointerCapture === 'function') {
			try {
				target.releasePointerCapture(event.pointerId);
			} catch {
				// ignore
			}
		}
		const next = config;
		resize = null;
		onConfigChange?.(next);
	}

	const formatCurrency = (amount: number, currency: string = 'CAD') =>
		new Intl.NumberFormat('en-CA', {
			style: 'currency',
			currency: currency || 'CAD'
		}).format(amount);

	const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

	type HoldingAccountBadge = {
		name: string;
		account_id?: string;
		percent_of_account: number;
	};

	type HoldingRowView = {
		id: string;
		security_id: string;
		security_symbol: string;
		security_name: string;
		currency: string;
		security_currency: string;
		quantity: number;
		average_cost: number | null;
		converted_average_cost: number | null;
		latest_price?: number;
		price_date?: string;
		total_value: number;
		unconverted_total_value: number;
		percent_of_total: number;
		profit_loss: number | null;
		unconverted_profit_loss: number | null;
		account_names: string[];
		accounts: HoldingAccountBadge[];
		ew_primary_target: number | null;
		ew_primary_upside: number | null;
		ew_cycle_target: number | null;
		ew_cycle_upside: number | null;
		valuation_lower: number | null;
		valuation_upper: number | null;
		valuation_lower_upside: number | null;
		valuation_upper_upside: number | null;
		valuation_updated_at: string | null;
	};

	// Fields shared by a single holding and a grouped holding.
	type HoldingRowSource = Omit<
		HoldingRowView,
		'percent_of_total' | 'account_names' | 'accounts' | `ew_${string}` | `valuation_${string}`
	>;

	const totalPortfolioValue = $derived(holdings.reduce((sum, h) => sum + (h.total_value ?? 0), 0));

	const accountTotals = $derived.by(() => {
		const map = new SvelteMap<string, number>();
		for (const h of holdings) {
			const key = h.account_name || h.account_id;
			if (key) {
				map.set(key, (map.get(key) ?? 0) + (h.total_value ?? 0));
			}
		}
		return map;
	});

	const toNumberOrNull = (value: unknown): number | null =>
		value === undefined || value === null ? null : Number(value);

	/** Per-account share of each holding, keyed by account name (or id). */
	function accountBadges(rows: UserHolding[]): HoldingAccountBadge[] {
		const byAccount = new SvelteMap<string, { name: string; account_id: string; value: number }>();
		for (const row of rows) {
			const key = row.account_name || row.account_id;
			if (!key) continue;
			const existing = byAccount.get(key);
			if (existing) {
				existing.value += row.total_value ?? 0;
			} else {
				byAccount.set(key, { name: key, account_id: row.account_id, value: row.total_value ?? 0 });
			}
		}
		return Array.from(byAccount, ([key, item]) => ({
			name: item.name,
			account_id: item.account_id,
			percent_of_account: calculatePercentOfAccount(item.value, accountTotals.get(key) ?? 0)
		}));
	}

	function toRowView(
		source: HoldingRowSource,
		rows: UserHolding[],
		account_names: string[]
	): HoldingRowView {
		const waves = elliottWaves?.[source.security_id];
		const ew_primary_target = getWaveTargetPrice(getLatestWaveCount(waves, 'primary'), 'wave5');
		const ew_cycle_target = getWaveTargetPrice(getLatestWaveCount(waves, 'cycle'), 'wave5');
		const valuation = valuations?.[source.security_id];
		const valuation_lower = toNumberOrNull(valuation?.lower_bound);
		const valuation_upper = toNumberOrNull(valuation?.upper_bound);
		const valuation_lower_upside = calculateUpsidePercentage(valuation_lower, source.latest_price);
		const valuation_upper_upside = calculateUpsidePercentage(valuation_upper, source.latest_price);
		const valuation_updated_at = valuation?.updated_at || valuation?.created_at || null;

		return {
			id: source.id,
			security_id: source.security_id,
			security_symbol: source.security_symbol,
			security_name: source.security_name,
			currency: source.currency,
			security_currency: source.security_currency,
			quantity: source.quantity,
			average_cost: source.average_cost,
			converted_average_cost: source.converted_average_cost,
			latest_price: source.latest_price,
			price_date: source.price_date,
			total_value: source.total_value,
			unconverted_total_value: source.unconverted_total_value,
			percent_of_total: calculatePercentOfTotal(source.total_value, totalPortfolioValue),
			profit_loss: source.profit_loss,
			unconverted_profit_loss: source.unconverted_profit_loss,
			account_names,
			accounts: accountBadges(rows),
			ew_primary_target,
			ew_primary_upside: calculateUpsidePercentage(ew_primary_target, source.latest_price),
			ew_cycle_target,
			ew_cycle_upside: calculateUpsidePercentage(ew_cycle_target, source.latest_price),
			valuation_lower,
			valuation_upper,
			valuation_lower_upside,
			valuation_upper_upside,
			valuation_updated_at
		};
	}

	const baseRows = $derived.by<HoldingRowView[]>(() =>
		groupBy === 'stock' || groupBy === 'company'
			? groupHoldings(holdings, 'stock').map((g) => toRowView(g, g.rows, g.account_names))
			: holdings.map((h) => toRowView(h, [h], h.account_name ? [h.account_name] : []))
	);

	function profitLossPercent(row: HoldingRowView): number | null {
		if (row.profit_loss === null || row.profit_loss === undefined) return null;
		const costBasis = row.quantity * (row.converted_average_cost ?? row.average_cost ?? 0);
		if (!costBasis || costBasis <= 0) return null;
		return (row.profit_loss / costBasis) * 100;
	}

	function getPillClass(changePercent: number): string {
		if (changePercent > 0) {
			return 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
		}
		if (changePercent < 0) {
			return 'text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20';
		}
		return 'text-muted-foreground bg-muted/40 border-border/40';
	}

	function formatUpsidePercent(percent: number): string {
		const rounded = Math.round(percent);
		const prefix = rounded > 0 ? '+' : '';
		return `${prefix}${rounded}%`;
	}

	function getUpsideClass(percent: number): string {
		if (percent > 0) return 'text-emerald-600 dark:text-emerald-400';
		if (percent < 0) return 'text-rose-600 dark:text-rose-400';
		return 'text-muted-foreground';
	}

	function getUpsideRangeClass(lower: number, upper: number): string {
		if (lower > 0 && upper > 0) return 'text-emerald-600 dark:text-emerald-400';
		if (lower < 0 && upper < 0) return 'text-rose-600 dark:text-rose-400';
		return '';
	}

	function valueFor(
		row: HoldingRowView,
		column: HoldingsTableColumnId
	): string | number | null | undefined {
		if (column === 'account_name') {
			return row.percent_of_total;
		}
		if (column === 'ew_primary_target') {
			return row.ew_primary_upside ?? row.ew_primary_target;
		}
		if (column === 'ew_cycle_target') {
			return row.ew_cycle_upside ?? row.ew_cycle_target;
		}
		if (column === 'valuation_range') {
			const { valuation_lower: lower, valuation_upper: upper } = row;
			return lower !== null && upper !== null && Number.isFinite(lower) && Number.isFinite(upper)
				? (lower + upper) / 2
				: null;
		}
		return row[column as keyof HoldingRowView] as string | number | null | undefined;
	}

	// Null/undefined cells always sort last, in both directions.
	const displayRows = $derived.by<HoldingRowView[]>(() =>
		[...baseRows].sort((a, b) => {
			const aVal = valueFor(a, sortColumn);
			const bVal = valueFor(b, sortColumn);

			const aNil =
				aVal === null || aVal === undefined || (typeof aVal === 'number' && !Number.isFinite(aVal));
			const bNil =
				bVal === null || bVal === undefined || (typeof bVal === 'number' && !Number.isFinite(bVal));

			if (aNil && bNil) return 0;
			if (aNil) return 1;
			if (bNil) return -1;

			const comparison =
				typeof aVal === 'string' && typeof bVal === 'string'
					? aVal.localeCompare(bVal)
					: (aVal as number) - (bVal as number);

			return sortDirection === 'asc' ? comparison : -comparison;
		})
	);

	// Borders live on cells (the table uses separate borders) so the sticky
	// security column carries its own borders while scrolling horizontally.
	const CELL = 'border-r border-b border-r-border/40 border-b-border px-4 py-2';

	function handleSort(column: HoldingsTableColumnId) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'desc';
		}
	}
</script>

{#snippet sortHeader(column: HoldingsTableColumn, width: number)}
	{@const label = column.label}
	<Table.Head
		data-testid={`column-header-${column.id === 'account_name' ? 'allocation' : column.id}`}
		class={`group/head relative h-10 cursor-pointer border-r border-b border-r-border/40 border-b-border px-4 py-2 transition-colors select-none hover:bg-muted/50 ${column.alignRight ? 'text-right' : ''}`}
		onclick={() => handleSort(column.id)}
	>
		<button
			type="button"
			class={`group flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground ${
				column.alignRight ? 'ml-auto' : ''
			}`}
			onclick={(event) => {
				event.stopPropagation();
				handleSort(column.id);
			}}
		>
			{label}
			{#if sortColumn === column.id}
				{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown size={12} />{/if}
			{:else}
				<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover/head:opacity-50" />
			{/if}
		</button>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<span
			role="separator"
			aria-orientation="vertical"
			aria-label={`Resize ${label} column`}
			aria-valuenow={width}
			data-testid={`column-resize-${column.id}`}
			class="absolute inset-y-0 right-0 z-20 w-1.5 cursor-col-resize touch-none border-r border-border/40 bg-transparent select-none hover:border-primary/70 hover:bg-primary/50"
			onpointerdown={(event) => handleResizePointerDown(event, column.id)}
			onpointermove={handleResizePointerMove}
			onpointerup={handleResizePointerUp}
			onpointercancel={handleResizePointerUp}
			onclick={(event) => event.stopPropagation()}
		></span>
	</Table.Head>
{/snippet}

{#snippet pillStack(
	percent: number | null,
	detail: string | null,
	pillTestId: string,
	detailTestId: string
)}
	{#if detail !== null}
		<div class="flex flex-col items-end gap-0.5 leading-tight">
			{#if percent !== null}
				<span
					data-testid={pillTestId}
					class={cn(
						'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
						getPillClass(percent)
					)}
				>
					{formatPercent(percent)}
				</span>
			{/if}
			<span data-testid={detailTestId} class="text-xs text-muted-foreground tabular-nums">
				{detail}
			</span>
		</div>
	{:else}
		<span class="text-sm text-muted-foreground">-</span>
	{/if}
{/snippet}

{#snippet accountBadge(account: HoldingAccountBadge)}
	<Badge variant="secondary" class="text-[10px] font-normal text-muted-foreground">
		<span class="text-[10px] font-normal text-muted-foreground">{account.name}</span>
		<span class="ml-1 text-muted-foreground/70"
			>{formatHoldingPercent(account.percent_of_account)}</span
		>
	</Badge>
{/snippet}

{#snippet holdingRow(row: HoldingRowView)}
	<!-- Opaque row tints: the sticky cell inherits the row's (animated) background. -->
	<Table.Row
		data-testid="holding-row"
		class="border-b-0 bg-background even:bg-table-row-striped hover:bg-table-row-hover"
	>
		{#if isVisible('security_symbol')}
			<Table.Cell class={cn(CELL, 'sticky left-0 z-10 bg-inherit')}>
				<a
					data-testid="security-link"
					href={resolve(`/security/${row.security_id}`)}
					class="flex w-fit flex-col rounded-md px-2 py-1 transition-colors hover:bg-background/60"
				>
					<span
						data-testid="security-symbol"
						class="inline-block text-sm leading-tight font-semibold text-primary"
					>
						{row.security_symbol}
					</span>
					<span class="text-[10px] leading-tight text-muted-foreground">{row.security_name}</span>
				</a>
			</Table.Cell>
		{/if}
		{#if isVisible('account_name')}
			<Table.Cell data-testid="account-cell" class={cn(CELL, 'text-sm')}>
				<div class="flex items-center gap-2">
					<span
						data-testid="percent-of-total"
						class="text-xs font-medium text-foreground tabular-nums"
					>
						{formatHoldingPercent(row.percent_of_total)}
					</span>
					{#if row.accounts.length === 0}
						<span class="text-xs text-muted-foreground">-</span>
					{:else}
						<div class="flex flex-wrap items-center gap-1">
							{#each row.accounts as account (account.account_id ?? account.name)}
								{#if onAccountClick && account.account_id}
									<button
										type="button"
										data-testid="account-badge"
										data-account-id={account.account_id}
										aria-label={`Filter by ${account.name}`}
										class="cursor-pointer rounded-full transition-opacity hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
										onclick={() => onAccountClick(account.account_id as string)}
									>
										{@render accountBadge(account)}
									</button>
								{:else}
									{@render accountBadge(account)}
								{/if}
							{/each}
						</div>
					{/if}
				</div>
			</Table.Cell>
		{/if}
		{#if isVisible('quantity')}
			<Table.Cell class={cn(CELL, 'text-right text-xs tabular-nums')}>
				{row.quantity.toLocaleString(undefined, {
					minimumFractionDigits: 0,
					maximumFractionDigits: 4
				})}
			</Table.Cell>
		{/if}
		{#if isVisible('latest_price')}
			<Table.Cell class={cn(CELL, 'text-right')}>
				<div
					class="flex flex-col items-end leading-tight"
					title={row.price_date ? `Snapshot from: ${row.price_date}` : undefined}
				>
					<span data-testid="latest-price" class="text-xs font-medium tabular-nums">
						{row.latest_price !== null && row.latest_price !== undefined
							? formatCurrency(row.latest_price, row.security_currency)
							: '-'}
					</span>
					<span data-testid="average-cost" class="text-[10px] text-muted-foreground tabular-nums">
						{row.average_cost !== null && row.average_cost !== undefined
							? formatCurrency(row.average_cost, row.security_currency)
							: '—'}
					</span>
				</div>
			</Table.Cell>
		{/if}
		{#if isVisible('total_value')}
			<Table.Cell class={cn(CELL, 'text-right')}>
				<div class="flex flex-col items-end leading-tight">
					<span class="text-sm font-medium tabular-nums">
						{formatCurrency(row.total_value, row.currency)}
					</span>
					{#if row.security_currency !== row.currency}
						<span class="text-[10px] text-muted-foreground/70 tabular-nums">
							{formatCurrency(row.unconverted_total_value, row.security_currency)}
						</span>
					{/if}
				</div>
			</Table.Cell>
		{/if}
		{#if isVisible('profit_loss')}
			<Table.Cell class={cn(CELL, 'text-right')}>
				{@render pillStack(
					profitLossPercent(row),
					row.profit_loss === null || row.profit_loss === undefined
						? null
						: `${row.profit_loss >= 0 ? '+' : ''}${formatCurrency(row.profit_loss, row.currency)}`,
					'profit-loss-percent',
					'profit-loss'
				)}
			</Table.Cell>
		{/if}
		{#if isVisible('ew_primary_target')}
			<Table.Cell class={cn(CELL, 'text-right')}>
				{@render pillStack(
					row.ew_primary_upside,
					row.ew_primary_target === null
						? null
						: formatCurrency(row.ew_primary_target, row.security_currency),
					'ew-primary-upside',
					'ew-primary-target'
				)}
			</Table.Cell>
		{/if}
		{#if isVisible('ew_cycle_target')}
			<Table.Cell class={cn(CELL, 'text-right')}>
				{@render pillStack(
					row.ew_cycle_upside,
					row.ew_cycle_target === null
						? null
						: formatCurrency(row.ew_cycle_target, row.security_currency),
					'ew-cycle-upside',
					'ew-cycle-target'
				)}
			</Table.Cell>
		{/if}
		{#if isVisible('valuation_range')}
			<Table.Cell data-testid="valuation-range-cell" class={cn(CELL, 'text-right')}>
				<button
					type="button"
					data-testid="valuation-edit-trigger"
					aria-label={`Edit valuation for ${row.security_symbol}`}
					class="ml-auto flex cursor-pointer flex-col items-end rounded-md px-2 py-1 text-right transition-colors hover:bg-background/60"
					onclick={() => handleValuationClick(row)}
				>
					{#if row.valuation_lower !== null && row.valuation_upper !== null}
						<div class="flex flex-col items-end gap-0.5 leading-tight">
							<span data-testid="valuation-range" class="text-xs font-medium tabular-nums">
								{formatValuationRange(row.valuation_lower, row.valuation_upper)}
							</span>
							{#if row.valuation_lower_upside !== null && row.valuation_upper_upside !== null}
								<span
									data-testid="valuation-upside-range"
									class={cn(
										'text-[10px] font-medium tabular-nums',
										getUpsideRangeClass(row.valuation_lower_upside, row.valuation_upper_upside)
									)}
								>
									<span class={getUpsideClass(row.valuation_lower_upside)}>
										{formatUpsidePercent(row.valuation_lower_upside)}
									</span>
									<span class="text-muted-foreground"> – </span>
									<span class={getUpsideClass(row.valuation_upper_upside)}>
										{formatUpsidePercent(row.valuation_upper_upside)}
									</span>
								</span>
							{/if}
							{#if row.valuation_updated_at}
								<span
									data-testid="valuation-updated-at"
									class="text-[10px] text-muted-foreground tabular-nums"
								>
									{formatDate(row.valuation_updated_at)}
								</span>
							{/if}
						</div>
					{:else}
						<span data-testid="valuation-range" class="text-xs font-medium tabular-nums"> — </span>
					{/if}
				</button>
			</Table.Cell>
		{/if}
	</Table.Row>
{/snippet}

<div class="w-full">
	<Table.Root class="border-separate border-spacing-0">
		<colgroup>
			{#each visibleColumns as column (column.id)}
				<col data-testid={`column-col-${column.id}`} style="width: {config.widths[column.id]}px;" />
			{/each}
		</colgroup>
		<Table.Header class="sticky top-0 z-10 bg-muted/30">
			<Table.Row class="hover:bg-transparent">
				{#each visibleColumns as column (column.id)}
					{@render sortHeader(column, config.widths[column.id])}
				{/each}
			</Table.Row>
		</Table.Header>
		<Table.Body class="[&_tr:last-child>td]:border-b-0">
			{#if isLoading}
				{#each SKELETON_ROW_INDEXES as rowIndex (rowIndex)}
					<Table.Row data-testid="skeleton-row">
						{#each visibleColumns as column (column.id)}
							<Table.Cell
								class={cn(
									'border-b border-b-border px-4 py-3',
									column.id === HOLDINGS_TABLE_STICKY_COLUMN_ID &&
										'sticky left-0 z-10 bg-background'
								)}
							>
								<div class="h-4 w-full animate-pulse rounded bg-muted"></div>
							</Table.Cell>
						{/each}
					</Table.Row>
				{/each}
			{:else if holdings.length === 0}
				<Table.Row data-testid="empty-state">
					<Table.Cell colspan={visibleColumnCount} class="px-8 py-16 text-center">
						<div class="flex flex-col items-center gap-2 opacity-50">
							<span class="text-3xl">📁</span>
							<p class="text-sm text-muted-foreground">{emptyMessage}</p>
						</div>
					</Table.Cell>
				</Table.Row>
			{:else}
				{#each displayRows as row (row.id)}
					{@render holdingRow(row)}
				{/each}
			{/if}
		</Table.Body>
	</Table.Root>
</div>

<ValuationModal
	modalState={valuationModalState}
	onSaved={(saved) => {
		const secId = saved.security_id || valuationModalState.data?.securityId;
		if (secId) {
			onValuationChange?.(secId, saved);
		}
	}}
/>
