<script lang="ts">
	import { resolve } from '$app/paths';
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
	import {
		HOLDINGS_TABLE_COLUMNS,
		HOLDINGS_TABLE_STICKY_COLUMN_ID,
		clampColumnWidth,
		normalizeHoldingsTableConfig,
		type HoldingsTableColumnId,
		type HoldingsTableColumn,
		type HoldingsTableConfig
	} from './holdings-table-columns';

	type Props = {
		holdings: UserHolding[];
		groupBy?: 'stock' | 'company' | null;
		isLoading?: boolean;
		emptyMessage?: string;
		tableConfig?: HoldingsTableConfig | null;
		onConfigChange?: (config: HoldingsTableConfig) => void;
		elliottWaves?: Record<string, SecurityElliottWaves> | null;
	};

	let {
		holdings,
		groupBy = null,
		isLoading = false,
		emptyMessage = 'No holdings yet.',
		tableConfig = null,
		onConfigChange,
		elliottWaves = null
	}: Props = $props();

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
		profit_loss: number | null;
		unconverted_profit_loss: number | null;
		account_names: string[];
		ew_primary_target: number | null;
		ew_primary_upside: number | null;
		ew_cycle_target: number | null;
		ew_cycle_upside: number | null;
	};

	const baseRows = $derived.by<HoldingRowView[]>(() => {
		if (groupBy === 'stock' || groupBy === 'company') {
			const groups = groupHoldings(holdings, 'stock');
			return groups.map((g) => {
				const primaryWave = getLatestWaveCount(elliottWaves?.[g.security_id], 'primary');
				const ew_primary_target = getWaveTargetPrice(primaryWave, 'wave5');
				const ew_primary_upside = calculateUpsidePercentage(ew_primary_target, g.latest_price);

				const cycleWave = getLatestWaveCount(elliottWaves?.[g.security_id], 'cycle');
				const ew_cycle_target = getWaveTargetPrice(cycleWave, 'wave5');
				const ew_cycle_upside = calculateUpsidePercentage(ew_cycle_target, g.latest_price);

				return {
					id: g.id,
					security_id: g.security_id,
					security_symbol: g.security_symbol,
					security_name: g.security_name,
					currency: g.currency,
					security_currency: g.security_currency,
					quantity: g.quantity,
					average_cost: g.average_cost,
					converted_average_cost: g.converted_average_cost,
					latest_price: g.latest_price,
					price_date: g.price_date,
					total_value: g.total_value,
					unconverted_total_value: g.unconverted_total_value,
					profit_loss: g.profit_loss,
					unconverted_profit_loss: g.unconverted_profit_loss,
					account_names: g.account_names,
					ew_primary_target,
					ew_primary_upside,
					ew_cycle_target,
					ew_cycle_upside
				};
			});
		}

		return holdings.map((row) => {
			const primaryWave = getLatestWaveCount(elliottWaves?.[row.security_id], 'primary');
			const ew_primary_target = getWaveTargetPrice(primaryWave, 'wave5');
			const ew_primary_upside = calculateUpsidePercentage(ew_primary_target, row.latest_price);

			const cycleWave = getLatestWaveCount(elliottWaves?.[row.security_id], 'cycle');
			const ew_cycle_target = getWaveTargetPrice(cycleWave, 'wave5');
			const ew_cycle_upside = calculateUpsidePercentage(ew_cycle_target, row.latest_price);

			return {
				id: row.id,
				security_id: row.security_id,
				security_symbol: row.security_symbol,
				security_name: row.security_name,
				currency: row.currency,
				security_currency: row.security_currency,
				quantity: row.quantity,
				average_cost: row.average_cost,
				converted_average_cost: row.converted_average_cost,
				latest_price: row.latest_price,
				price_date: row.price_date,
				total_value: row.total_value,
				unconverted_total_value: row.unconverted_total_value,
				profit_loss: row.profit_loss,
				unconverted_profit_loss: row.unconverted_profit_loss,
				account_names: row.account_name ? [row.account_name] : [],
				ew_primary_target,
				ew_primary_upside,
				ew_cycle_target,
				ew_cycle_upside
			};
		});
	});

	function profitLossPercent(row: HoldingRowView): number | null {
		if (row.profit_loss === null || row.profit_loss === undefined) return null;
		const costBasis = row.quantity * (row.converted_average_cost ?? row.average_cost ?? 0);
		if (!costBasis || costBasis <= 0) return null;
		return (row.profit_loss / costBasis) * 100;
	}

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

	function valueFor(
		row: HoldingRowView,
		column: HoldingsTableColumnId
	): string | number | null | undefined {
		if (column === 'account_name') {
			return row.account_names.length > 0 ? row.account_names.join(', ') : null;
		}
		if (column === 'ew_primary_target') {
			return row.ew_primary_upside ?? row.ew_primary_target;
		}
		if (column === 'ew_cycle_target') {
			return row.ew_cycle_upside ?? row.ew_cycle_target;
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
	{@const label = column.id === 'account_name' && groupBy ? 'Accounts' : column.label}
	<Table.Head
		class={`group/head relative h-10 cursor-pointer border-r border-border/40 px-4 py-2 transition-colors select-none hover:bg-muted/50 ${column.alignRight ? 'text-right' : ''}`}
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

{#snippet holdingRow(row: HoldingRowView)}
	<Table.Row
		data-testid="holding-row"
		class="group border-b border-border transition-colors even:bg-muted/50 hover:bg-muted/80"
	>
		{#if isVisible('security_symbol')}
			<Table.Cell
				class="sticky left-0 z-10 border-r border-border/40 bg-background px-4 py-2 group-even:bg-muted/50 group-hover:bg-muted/80 group-even:group-hover:bg-muted/80"
			>
				<a
					data-testid="security-link"
					href={resolve(`/security/${row.security_id}`)}
					class="flex w-fit flex-col rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-accent-foreground"
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
			<Table.Cell data-testid="account-cell" class="border-r border-border/40 px-4 py-2 text-sm">
				{#if row.account_names.length === 0}
					-
				{:else}
					<div class="flex flex-wrap items-center gap-1">
						{#each row.account_names as name (name)}
							<Badge variant="secondary" class="text-[10px] font-normal text-muted-foreground">
								{name}
							</Badge>
						{/each}
					</div>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('quantity')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right text-xs tabular-nums">
				{row.quantity.toLocaleString(undefined, {
					minimumFractionDigits: 0,
					maximumFractionDigits: 4
				})}
			</Table.Cell>
		{/if}
		{#if isVisible('average_cost')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
				<span class="text-xs text-muted-foreground tabular-nums">
					{row.average_cost !== null && row.average_cost !== undefined
						? formatCurrency(row.average_cost, row.security_currency)
						: '-'}
				</span>
			</Table.Cell>
		{/if}
		{#if isVisible('latest_price')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
				{#if row.latest_price !== null && row.latest_price !== undefined}
					<div
						class="flex flex-col items-end leading-tight"
						title={row.price_date ? `Snapshot from: ${row.price_date}` : undefined}
					>
						<span class="text-xs font-medium tabular-nums">
							{formatCurrency(row.latest_price, row.security_currency)}
						</span>
					</div>
				{:else}
					<span class="text-xs text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('total_value')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
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
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
				{#if row.profit_loss !== null && row.profit_loss !== undefined}
					{@const plPercent = profitLossPercent(row)}
					<div class="flex flex-col items-end gap-0.5 leading-tight">
						{#if plPercent !== null}
							<span
								data-testid="profit-loss-percent"
								class={cn(
									'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
									getPillClass(plPercent)
								)}
							>
								{formatPercent(plPercent)}
							</span>
						{/if}
						<span data-testid="profit-loss" class="text-xs text-muted-foreground tabular-nums">
							{row.profit_loss >= 0 ? '+' : ''}{formatCurrency(row.profit_loss, row.currency)}
						</span>
					</div>
				{:else}
					<span class="text-sm text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('ew_primary_target')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
				{#if row.ew_primary_target !== null && row.ew_primary_target !== undefined}
					<div class="flex flex-col items-end gap-0.5 leading-tight">
						{#if row.ew_primary_upside !== null && row.ew_primary_upside !== undefined}
							<span
								data-testid="ew-primary-upside"
								class={cn(
									'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
									getPillClass(row.ew_primary_upside)
								)}
							>
								{formatPercent(row.ew_primary_upside)}
							</span>
						{/if}
						<span
							data-testid="ew-primary-target"
							class="text-xs text-muted-foreground tabular-nums"
						>
							{formatCurrency(row.ew_primary_target, row.security_currency)}
						</span>
					</div>
				{:else}
					<span class="text-sm text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('ew_cycle_target')}
			<Table.Cell class="border-r border-border/40 px-4 py-2 text-right">
				{#if row.ew_cycle_target !== null && row.ew_cycle_target !== undefined}
					<div class="flex flex-col items-end gap-0.5 leading-tight">
						{#if row.ew_cycle_upside !== null && row.ew_cycle_upside !== undefined}
							<span
								data-testid="ew-cycle-upside"
								class={cn(
									'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
									getPillClass(row.ew_cycle_upside)
								)}
							>
								{formatPercent(row.ew_cycle_upside)}
							</span>
						{/if}
						<span data-testid="ew-cycle-target" class="text-xs text-muted-foreground tabular-nums">
							{formatCurrency(row.ew_cycle_target, row.security_currency)}
						</span>
					</div>
				{:else}
					<span class="text-sm text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
	</Table.Row>
{/snippet}

<div class="w-full">
	<Table.Root>
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
		<Table.Body>
			{#if isLoading}
				{#each SKELETON_ROW_INDEXES as rowIndex (rowIndex)}
					<Table.Row data-testid="skeleton-row">
						{#each visibleColumns as column (column.id)}
							<Table.Cell
								class={`px-4 py-3 ${
									column.id === HOLDINGS_TABLE_STICKY_COLUMN_ID
										? 'sticky left-0 z-10 bg-background'
										: ''
								}`}
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
