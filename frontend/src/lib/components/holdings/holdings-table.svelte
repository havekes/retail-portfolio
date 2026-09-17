<script lang="ts">
	import { resolve } from '$app/paths';
	import { SvelteSet } from 'svelte/reactivity';
	import type { Holding } from '$lib/types/account';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Settings2 from '@lucide/svelte/icons/settings-2';
	import {
		HOLDINGS_TABLE_COLUMNS,
		HOLDINGS_TABLE_STICKY_COLUMN_ID,
		clampColumnWidth,
		normalizeHoldingsTableConfig,
		type HoldingsTableColumnId,
		type HoldingsTableColumn,
		type HoldingsTableConfig
	} from './holdings-table-columns';

	// `UserHolding` (HOLDINGS-T02) is not merged yet; type against the existing
	// `Holding` plus the account fields the user-wide table needs. T02 can replace
	// this alias with `UserHolding` once it lands.
	type HoldingsRow = Holding & { account_id?: string; account_name?: string };

	type Props = {
		holdings: HoldingsRow[];
		groupBy?: 'company' | null;
		isLoading?: boolean;
		emptyMessage?: string;
		tableConfig?: HoldingsTableConfig | null;
		onConfigChange?: (config: HoldingsTableConfig) => void;
	};

	let {
		holdings,
		groupBy = null,
		isLoading = false,
		emptyMessage = 'No holdings yet.',
		tableConfig = null,
		onConfigChange
	}: Props = $props();

	// Writable derived: normalizes the consumer's config, but a drag/toggle can
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

	// SvelteSet keeps collapse state reactive without manual reassignment.
	let collapsedGroups = new SvelteSet<string>();

	type Resize = { column: HoldingsTableColumnId; startX: number; startWidth: number };
	let resize = $state<Resize | null>(null);

	function commitConfig(next: HoldingsTableConfig) {
		config = next;
		onConfigChange?.(next);
	}

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

	function toggleColumn(column: HoldingsTableColumnId) {
		if (column === HOLDINGS_TABLE_STICKY_COLUMN_ID) return;
		const visible = config.visible.includes(column)
			? config.visible.filter((id) => id !== column)
			: HOLDINGS_TABLE_COLUMNS.map((c) => c.id).filter(
					(id) => id === column || config.visible.includes(id)
				);
		commitConfig({ ...config, visible });
	}

	const formatCurrency = (amount: number, currency: string) =>
		new Intl.NumberFormat('en-CA', {
			style: 'currency',
			currency
		}).format(amount);

	const formatNumber = (amount: number) =>
		new Intl.NumberFormat('en-CA', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2
		}).format(amount);

	const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

	// Same formula as the account-scoped table: gain relative to the converted cost
	// basis. Null when there is nothing meaningful to divide by.
	function profitLossPercent(row: HoldingsRow): number | null {
		if (row.profit_loss === null || row.profit_loss === undefined) return null;
		if (!row.average_cost || row.average_cost <= 0) return null;
		const costBasis = row.quantity * (row.converted_average_cost ?? 0);
		if (!costBasis) return null;
		return (row.profit_loss / costBasis) * 100;
	}

	function valueFor(
		row: HoldingsRow,
		column: HoldingsTableColumnId
	): string | number | null | undefined {
		if (column === 'profit_loss_percent') return profitLossPercent(row);
		return row[column];
	}

	// Null/undefined cells always sort last, in both directions (lifted from the
	// account-scoped table).
	const sortedHoldings = $derived.by(() =>
		[...holdings].sort((a, b) => {
			const aVal = valueFor(a, sortColumn);
			const bVal = valueFor(b, sortColumn);

			if (aVal === null || aVal === undefined) return 1;
			if (bVal === null || bVal === undefined) return -1;

			const comparison =
				typeof aVal === 'string' && typeof bVal === 'string'
					? aVal.localeCompare(bVal)
					: (aVal as number) - (bVal as number);

			return sortDirection === 'asc' ? comparison : -comparison;
		})
	);

	// Company key is the security name. Group order follows first appearance in the
	// currently sorted rows — group headers are never sorted by their aggregates in
	// this ticket.
	type HoldingGroup = { key: string; name: string; rows: HoldingsRow[] };

	const groupedHoldings = $derived.by<HoldingGroup[] | null>(() => {
		if (groupBy !== 'company') return null;

		const groups: HoldingGroup[] = [];
		const indexByKey: Record<string, number> = {};

		for (const row of sortedHoldings) {
			const key = row.security_name;
			let index = indexByKey[key];
			if (index === undefined) {
				index = groups.length;
				indexByKey[key] = index;
				groups.push({ key, name: row.security_name, rows: [] });
			}
			groups[index].rows.push(row);
		}

		return groups;
	});

	function groupTotals(rows: HoldingsRow[]) {
		let totalValue = 0;
		let profitLoss = 0;
		let costBasis = 0;
		let hasProfitLoss = false;

		for (const row of rows) {
			totalValue += row.total_value;
			if (row.profit_loss !== null && row.profit_loss !== undefined) {
				hasProfitLoss = true;
				profitLoss += row.profit_loss;
				if (row.average_cost !== null && row.average_cost > 0) {
					costBasis += row.quantity * (row.converted_average_cost ?? 0);
				}
			}
		}

		return {
			totalValue,
			profitLoss,
			hasProfitLoss,
			// Weighted P/L % across the group's converted cost basis.
			profitLossPercent: hasProfitLoss && costBasis ? (profitLoss / costBasis) * 100 : null
		};
	}

	function handleSort(column: HoldingsTableColumnId) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'desc';
		}
	}

	function toggleGroup(key: string) {
		if (collapsedGroups.has(key)) {
			collapsedGroups.delete(key);
		} else {
			collapsedGroups.add(key);
		}
	}
</script>

{#snippet sortHeader(column: HoldingsTableColumn, width: number)}
	<Table.Head class={`relative h-10 px-4 py-2 ${column.alignRight ? 'text-right' : ''}`}>
		<button
			type="button"
			class={`group flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground ${
				column.alignRight ? 'ml-auto' : ''
			}`}
			onclick={() => handleSort(column.id)}
		>
			{column.label}
			{#if sortColumn === column.id}
				{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown size={12} />{/if}
			{:else}
				<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
			{/if}
		</button>
		<span
			role="separator"
			aria-orientation="vertical"
			aria-label={`Resize ${column.label} column`}
			aria-valuenow={width}
			data-testid={`column-resize-${column.id}`}
			class="absolute inset-y-0 right-0 z-20 w-1.5 cursor-col-resize touch-none bg-transparent select-none hover:bg-primary/50"
			onpointerdown={(event) => handleResizePointerDown(event, column.id)}
			onpointermove={handleResizePointerMove}
			onpointerup={handleResizePointerUp}
			onpointercancel={handleResizePointerUp}
		></span>
	</Table.Head>
{/snippet}

{#snippet holdingRow(row: HoldingsRow)}
	<Table.Row
		data-testid="holding-row"
		class="border-b-muted/10 transition-all even:bg-muted/30 hover:bg-muted/10"
	>
		{#if isVisible('security_symbol')}
			<Table.Cell class="sticky left-0 z-10 bg-background px-4 py-2">
				<a
					data-testid="security-link"
					href={resolve(`/security/${row.security_id}`)}
					class="group flex w-fit flex-col"
				>
					<span
						data-testid="security-symbol"
						class="inline-block text-sm leading-tight font-semibold text-primary group-hover:underline"
					>
						{row.security_symbol}
					</span>
					<span class="text-[10px] leading-tight text-muted-foreground">{row.security_name}</span>
				</a>
			</Table.Cell>
		{/if}
		{#if isVisible('account_name')}
			<Table.Cell data-testid="account-cell" class="px-4 py-2 text-sm">
				{row.account_name ?? '-'}
			</Table.Cell>
		{/if}
		{#if isVisible('quantity')}
			<Table.Cell class="px-4 py-2 text-right text-sm tabular-nums">
				{row.quantity.toLocaleString(undefined, {
					minimumFractionDigits: 0,
					maximumFractionDigits: 4
				})}
			</Table.Cell>
		{/if}
		{#if isVisible('average_cost')}
			<Table.Cell class="px-4 py-2 text-right">
				<div class="flex flex-col items-end leading-tight">
					<span class="text-xs text-muted-foreground tabular-nums">
						{row.average_cost !== null && row.average_cost !== undefined
							? formatCurrency(row.average_cost, row.security_currency)
							: '-'}
					</span>
					{#if row.security_currency !== row.currency && row.converted_average_cost}
						<span class="text-[10px] text-muted-foreground/60 tabular-nums">
							{formatCurrency(row.converted_average_cost, row.currency)}
						</span>
					{/if}
				</div>
			</Table.Cell>
		{/if}
		{#if isVisible('latest_price')}
			<Table.Cell class="px-4 py-2 text-right">
				{#if row.latest_price !== null && row.latest_price !== undefined}
					<div
						class="flex flex-col items-end leading-tight"
						title={row.price_date ? `Snapshot from: ${row.price_date}` : undefined}
					>
						<span class="text-xs font-medium tabular-nums">
							{formatCurrency(row.latest_price, row.security_currency)}
						</span>
						{#if row.security_currency !== row.currency && row.converted_latest_price}
							<span class="text-[10px] text-muted-foreground/60 tabular-nums">
								{formatCurrency(row.converted_latest_price, row.currency)}
							</span>
						{/if}
					</div>
				{:else}
					<span class="text-xs text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('total_value')}
			<Table.Cell class="px-4 py-2 text-right">
				<div class="flex flex-col items-end leading-tight">
					<span class="text-sm font-medium tabular-nums">
						{formatCurrency(row.unconverted_total_value, row.security_currency)}
					</span>
					{#if row.security_currency !== row.currency}
						<span class="text-[10px] text-muted-foreground/70 tabular-nums">
							{formatCurrency(row.total_value, row.currency)}
						</span>
					{/if}
				</div>
			</Table.Cell>
		{/if}
		{#if isVisible('profit_loss')}
			<Table.Cell class="px-4 py-2 text-right">
				{#if row.profit_loss !== null && row.profit_loss !== undefined}
					<div class="flex flex-col items-end leading-tight">
						<span
							data-testid="profit-loss"
							class={`text-sm tabular-nums ${
								row.profit_loss >= 0 ? 'text-emerald-600' : 'text-rose-600'
							}`}
						>
							{row.profit_loss >= 0 ? '+' : ''}{formatCurrency(
								row.unconverted_profit_loss ?? 0,
								row.security_currency
							)}
						</span>
						{#if row.security_currency !== row.currency}
							<span
								class={`text-[10px] tabular-nums ${
									row.profit_loss >= 0 ? 'text-emerald-600/70' : 'text-rose-600/70'
								}`}
							>
								{row.profit_loss >= 0 ? '+' : ''}{formatCurrency(row.profit_loss, row.currency)}
							</span>
						{/if}
					</div>
				{:else}
					<span class="text-sm text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
		{#if isVisible('profit_loss_percent')}
			<Table.Cell class="px-4 py-2 text-right">
				{@const plPercent = profitLossPercent(row)}
				{#if plPercent !== null}
					<span
						data-testid="profit-loss-percent"
						class={`text-sm tabular-nums ${plPercent >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
					>
						{formatPercent(plPercent)}
					</span>
				{:else}
					<span class="text-sm text-muted-foreground">-</span>
				{/if}
			</Table.Cell>
		{/if}
	</Table.Row>
{/snippet}

<div class="w-full">
	<div class="flex items-center justify-end border-b px-2 py-1">
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props })}
					<button
						{...props}
						type="button"
						data-testid="column-visibility-trigger"
						aria-label="Toggle columns"
						title="Toggle columns"
						class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
					>
						<Settings2 size={14} />
						Columns
					</button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end" class="w-44">
				<DropdownMenu.Label>Visible columns</DropdownMenu.Label>
				<DropdownMenu.Separator />
				{#each HOLDINGS_TABLE_COLUMNS as column (column.id)}
					<DropdownMenu.CheckboxItem
						checked={isVisible(column.id)}
						disabled={column.id === HOLDINGS_TABLE_STICKY_COLUMN_ID}
						onCheckedChange={() => toggleColumn(column.id)}
						data-testid={`column-toggle-${column.id}`}
					>
						{column.label}
					</DropdownMenu.CheckboxItem>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>
	<Table.Root>
		<colgroup>
			{#each visibleColumns as column (column.id)}
				<col data-testid={`column-col-${column.id}`} style="width: {config.widths[column.id]}px;" />
			{/each}
		</colgroup>
		<Table.Header class="sticky top-0 z-10 bg-muted/30">
			<Table.Row>
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
			{:else if groupedHoldings}
				{#each groupedHoldings as group (group.key)}
					{@const totals = groupTotals(group.rows)}
					{@const collapsed = collapsedGroups.has(group.key)}
					<Table.Row data-testid="group-row" class="bg-muted/40 hover:bg-muted/50">
						<Table.Cell colspan={visibleColumnCount} class="p-0">
							<button
								type="button"
								data-testid="group-header"
								aria-expanded={!collapsed}
								class="flex w-full items-center gap-2 px-4 py-2 text-left"
								onclick={() => toggleGroup(group.key)}
							>
								{#if collapsed}<ChevronRight size={14} />{:else}<ChevronDown size={14} />{/if}
								<span class="text-sm font-semibold">{group.name}</span>
								<span class="text-xs text-muted-foreground">
									{group.rows.length}
									{group.rows.length === 1 ? 'holding' : 'holdings'}
								</span>
								<span class="ml-auto text-xs text-muted-foreground tabular-nums">
									Σ {formatNumber(totals.totalValue)}
								</span>
								{#if totals.hasProfitLoss}
									<span
										data-testid="group-profit-loss"
										class={`text-xs tabular-nums ${
											totals.profitLoss >= 0 ? 'text-emerald-600' : 'text-rose-600'
										}`}
									>
										Σ {totals.profitLoss >= 0 ? '+' : ''}{formatNumber(totals.profitLoss)}
										{#if totals.profitLossPercent !== null}
											({formatPercent(totals.profitLossPercent)})
										{/if}
									</span>
								{/if}
							</button>
						</Table.Cell>
					</Table.Row>
					{#if !collapsed}
						{#each group.rows as row (row.id)}
							{@render holdingRow(row)}
						{/each}
					{/if}
				{/each}
			{:else}
				{#each sortedHoldings as row (row.id)}
					{@render holdingRow(row)}
				{/each}
			{/if}
		</Table.Body>
	</Table.Root>
</div>
