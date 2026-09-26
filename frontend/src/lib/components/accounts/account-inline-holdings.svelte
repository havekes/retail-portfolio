<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Holding } from '@/types/account';
	import * as Table from '$lib/components/ui/table/index.js';

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
				currency: currency
			}).format(amount);
		} catch {
			return `$${amount.toFixed(2)}`;
		}
	};
</script>

<div class="w-full overflow-x-auto">
	<Table.Root>
		<Table.Header>
			<Table.Row class="border-b border-border/50">
				<Table.Head class="h-9 px-4 py-2 text-xs font-medium">Symbol</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Quantity</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Price</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Total Value</Table.Head>
				<Table.Head class="h-9 px-4 py-2 text-right text-xs font-medium">Return</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each holdings as holding (holding.id)}
				<Table.Row class="border-b border-border/30 hover:bg-muted/50">
					<Table.Cell class="px-4 py-2">
						<a href={resolve(`/security/${holding.security_id}`)} class="group flex w-fit flex-col">
							<span class="text-sm font-semibold text-primary group-hover:underline">
								{holding.security_symbol}
							</span>
							{#if holding.security_name}
								<span class="max-w-[180px] truncate text-[10px] text-muted-foreground">
									{holding.security_name}
								</span>
							{/if}
						</a>
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm tabular-nums">
						{holding.quantity.toLocaleString(undefined, {
							minimumFractionDigits: 0,
							maximumFractionDigits: 4
						})}
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm text-muted-foreground tabular-nums">
						{holding.latest_price !== undefined && holding.latest_price !== null
							? formatCurrency(holding.latest_price, holding.security_currency || accountCurrency)
							: '-'}
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm font-medium tabular-nums">
						{formatCurrency(holding.total_value, accountCurrency)}
					</Table.Cell>
					<Table.Cell class="px-4 py-2 text-right text-sm tabular-nums">
						{#if holding.profit_loss !== null && holding.profit_loss !== undefined}
							<span
								class={holding.profit_loss >= 0
									? 'font-medium text-emerald-600 dark:text-emerald-400'
									: 'font-medium text-rose-600 dark:text-rose-400'}
							>
								{holding.profit_loss >= 0 ? '+' : ''}{formatCurrency(
									holding.profit_loss,
									accountCurrency
								)}
							</span>
						{:else}
							<span class="text-muted-foreground">-</span>
						{/if}
					</Table.Cell>
				</Table.Row>
			{/each}
			{#if holdings.length === 0}
				<Table.Row>
					<Table.Cell colspan={5} class="px-4 py-6 text-center text-sm text-muted-foreground">
						No holdings found for this account.
					</Table.Cell>
				</Table.Row>
			{/if}
		</Table.Body>
	</Table.Root>
</div>
