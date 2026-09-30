<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Holding } from '@/types/account';
	import * as Table from '$lib/components/ui/table/index.js';
	import { cn } from '$lib/utils';

	let {
		holdings,
		accountCurrency
	}: {
		holdings: Holding[];
		accountCurrency: string;
	} = $props();

	const formatCurrency = (amount: number, currency: string) => {
		try {
			return new Intl.NumberFormat('en-CA', {
				style: 'currency',
				currency: currency || 'CAD'
			}).format(amount);
		} catch {
			return `$${amount.toFixed(2)}`;
		}
	};

	const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

	const profitLossPercent = (holding: Holding): number | null => {
		if (holding.profit_loss === null || holding.profit_loss === undefined) return null;
		const costBasis =
			holding.quantity * (holding.converted_average_cost ?? holding.average_cost ?? 0);
		if (!costBasis || costBasis <= 0) return null;
		return (holding.profit_loss / costBasis) * 100;
	};

	const getPillClass = (changePercent: number | null | undefined): string => {
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
	};
</script>

<div class="w-full overflow-x-auto">
	<Table.Root>
		<Table.Header>
			<Table.Row class="border-b border-border/50">
				<Table.Head class="h-9 px-4 py-2 text-xs font-medium">Symbol</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Account Value</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Price</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Return</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each holdings as holding (holding.id)}
				<Table.Row class="border-b border-border/30 hover:bg-muted/50">
					<Table.Cell class="px-4 py-2">
						<a
							href={resolve(`/security/${holding.security_id}`)}
							class="group -mx-2 -my-1 flex w-full flex-col rounded-md px-2 py-1 transition-colors hover:bg-background/60 dark:hover:bg-background/60"
						>
							<span class="text-sm font-semibold text-primary">
								{holding.security_symbol}
							</span>
							{#if holding.security_name}
								<span class="max-w-[180px] truncate text-[10px] text-muted-foreground">
									{holding.security_name}
								</span>
							{/if}
						</a>
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm font-medium tabular-nums">
						{formatCurrency(holding.total_value, accountCurrency)}
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm text-muted-foreground tabular-nums">
						{holding.latest_price !== undefined && holding.latest_price !== null
							? formatCurrency(holding.latest_price, holding.security_currency || accountCurrency)
							: '-'}
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm tabular-nums">
						{#if holding.profit_loss !== null && holding.profit_loss !== undefined}
							{@const plPercent = profitLossPercent(holding)}
							<div class="flex flex-col items-end gap-0.5 leading-tight">
								{#if plPercent !== null}
									<span
										class={cn(
											'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums',
											getPillClass(plPercent)
										)}
									>
										{formatPercent(plPercent)}
									</span>
								{/if}
								<span class="text-xs text-muted-foreground tabular-nums">
									{holding.profit_loss >= 0 ? '+' : ''}{formatCurrency(
										holding.profit_loss,
										accountCurrency
									)}
								</span>
							</div>
						{:else}
							<span class="text-muted-foreground">-</span>
						{/if}
					</Table.Cell>
				</Table.Row>
			{/each}
			{#if holdings.length === 0}
				<Table.Row>
					<Table.Cell colspan={4} class="px-4 py-6 text-center text-sm text-muted-foreground">
						No holdings found for this account.
					</Table.Cell>
				</Table.Row>
			{/if}
		</Table.Body>
	</Table.Root>
</div>
