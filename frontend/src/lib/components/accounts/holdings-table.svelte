<script lang="ts">
	import type { Holding } from '@/types/account';
	import * as Table from '$lib/components/ui/table/index.js';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';
	import { resolve } from '$app/paths';

	let { holdings, totalAccountValue }: { holdings: Holding[]; totalAccountValue: number } =
		$props();

	let sortColumn = $state<keyof Holding>('total_value');
	let sortDirection = $state<'asc' | 'desc'>('desc');

	const sortedHoldings = $derived.by(() => {
		return [...holdings].sort((a, b) => {
			const aVal = a[sortColumn];
			const bVal = b[sortColumn];

			if (aVal === null || aVal === undefined) return 1;
			if (bVal === null || bVal === undefined) return -1;

			const comparison =
				typeof aVal === 'string' && typeof bVal === 'string'
					? aVal.localeCompare(bVal)
					: (aVal as number) - (bVal as number);

			return sortDirection === 'asc' ? comparison : -comparison;
		});
	});

	function handleSort(column: keyof Holding) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'desc';
		}
	}

	const formatCurrency = (amount: number, currency: string) => {
		return new Intl.NumberFormat('en-CA', {
			style: 'currency',
			currency: currency
		}).format(amount);
	};
</script>

<div class="w-full">
	<Table.Root>
		<Table.Header class="sticky top-0 z-10 bg-muted/30">
			<Table.Row>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('security_symbol')}
					>
						Security
						{#if sortColumn === 'security_symbol'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group ml-auto flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('quantity')}
					>
						Shares
						{#if sortColumn === 'quantity'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group ml-auto flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('average_cost')}
					>
						Avg Cost
						{#if sortColumn === 'average_cost'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group ml-auto flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('latest_price')}
					>
						Price
						{#if sortColumn === 'latest_price'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group ml-auto flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('total_value')}
					>
						Total Value
						{#if sortColumn === 'total_value'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
				<Table.Head class="h-10 px-8 py-2">
					<button
						class="group ml-auto flex items-center gap-2 text-xs font-medium transition-colors hover:text-foreground"
						onclick={() => handleSort('profit_loss')}
					>
						Profit/Loss
						{#if sortColumn === 'profit_loss'}
							{#if sortDirection === 'asc'}<ChevronUp size={12} />{:else}<ChevronDown
									size={12}
								/>{/if}
						{:else}
							<ArrowUpDown size={12} class="opacity-0 transition-opacity group-hover:opacity-50" />
						{/if}
					</button>
				</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each sortedHoldings as holding (holding.id)}
				<Table.Row
					class="group border-b-muted/10 transition-all even:bg-muted/30 hover:bg-muted/10"
				>
					<Table.Cell class="px-8 py-2">
						<a href={resolve(`/security/${holding.security_id}`)} class="group flex w-fit flex-col">
							<span
								class="inline-block text-sm leading-tight font-semibold text-primary group-hover:underline"
							>
								{holding.security_symbol}
							</span>
							<span class="text-[10px] leading-tight text-muted-foreground">
								{holding.security_name}
							</span>
						</a>
					</Table.Cell>
					<Table.Cell class="px-8 py-2 text-right text-sm tabular-nums">
						{holding.quantity.toLocaleString(undefined, {
							minimumFractionDigits: 0,
							maximumFractionDigits: 4
						})}
					</Table.Cell>
					<Table.Cell class="px-8 py-2 text-right">
						<div class="flex flex-col items-end leading-tight">
							<span class="text-xs text-muted-foreground tabular-nums">
								{holding.average_cost !== null
									? formatCurrency(holding.average_cost, holding.security_currency)
									: '-'}
							</span>
							{#if holding.security_currency !== holding.currency && holding.converted_average_cost}
								<span class="text-[10px] text-muted-foreground/60 tabular-nums">
									{formatCurrency(holding.converted_average_cost, holding.currency)}
								</span>
							{/if}
						</div>
					</Table.Cell>
					<Table.Cell class="px-8 py-2 text-right">
						{#if holding.latest_price}
							<Tooltip.Provider>
								<Tooltip.Root delayDuration={200}>
									<Tooltip.Trigger class="cursor-default">
										<div class="flex flex-col items-end leading-tight">
											<span class="text-xs font-medium tabular-nums">
												{formatCurrency(holding.latest_price, holding.security_currency)}
											</span>
											{#if holding.security_currency !== holding.currency && holding.converted_latest_price}
												<span class="text-[10px] text-muted-foreground/60 tabular-nums">
													{formatCurrency(holding.converted_latest_price, holding.currency)}
												</span>
											{/if}
										</div>
									</Tooltip.Trigger>
									<Tooltip.Content>
										<p class="text-[10px]">
											Snapshot from: {holding.price_date || 'Unknown'}
										</p>
									</Tooltip.Content>
								</Tooltip.Root>
							</Tooltip.Provider>
						{:else}
							<span class="text-xs text-muted-foreground">-</span>
						{/if}
					</Table.Cell>
					<Table.Cell class="px-8 py-2 text-right">
						<div class="flex flex-col items-end leading-tight">
							<div class="flex items-center justify-end gap-1.5">
								<span class="text-sm font-medium tabular-nums">
									{formatCurrency(holding.unconverted_total_value, holding.security_currency)}
								</span>
							</div>
							{#if holding.security_currency !== holding.currency}
								<span class="text-[10px] text-muted-foreground/70 tabular-nums">
									{formatCurrency(holding.total_value, holding.currency)}
								</span>
							{/if}
							{#if totalAccountValue > 0}
								<span class="mt-0.5 text-[10px] text-muted-foreground/50 tabular-nums">
									{((holding.total_value / totalAccountValue) * 100).toFixed(2)}%
								</span>
							{/if}
						</div>
					</Table.Cell>
					<Table.Cell class="px-8 py-2 text-right">
						{#if holding.profit_loss !== null}
							<div class="flex flex-col items-end leading-tight">
								<span
									class={`text-sm tabular-nums ${holding.profit_loss >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
								>
									{holding.profit_loss >= 0 ? '+' : ''}{formatCurrency(
										holding.unconverted_profit_loss ?? 0,
										holding.security_currency
									)}
								</span>
								{#if holding.security_currency !== holding.currency}
									<span
										class={`text-[10px] tabular-nums ${holding.profit_loss >= 0 ? 'text-emerald-600/70' : 'text-rose-600/70'}`}
									>
										{holding.profit_loss >= 0 ? '+' : ''}{formatCurrency(
											holding.profit_loss,
											holding.currency
										)}
									</span>
								{/if}
								{#if holding.average_cost && holding.average_cost > 0}
									{@const plPercent =
										(holding.profit_loss /
											(holding.quantity * (holding.converted_average_cost ?? 0))) *
										100}
									<span
										class={`mt-0.5 text-[10px] tabular-nums ${holding.profit_loss >= 0 ? 'text-emerald-600/50' : 'text-rose-600/50'}`}
									>
										{holding.profit_loss >= 0 ? '+' : ''}{plPercent.toFixed(2)}%
									</span>
								{/if}
							</div>
						{:else}
							<span class="text-sm text-muted-foreground">-</span>
						{/if}
					</Table.Cell>
				</Table.Row>
			{/each}
			{#if holdings.length === 0}
				<Table.Row>
					<Table.Cell colspan={6} class="px-8 py-16 text-center">
						<div class="flex flex-col items-center gap-2 opacity-50">
							<span class="text-3xl">📁</span>
							<p class="text-sm text-muted-foreground">No holdings found for this account.</p>
						</div>
					</Table.Cell>
				</Table.Row>
			{/if}
		</Table.Body>
	</Table.Root>
</div>
