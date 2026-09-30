<script lang="ts">
	import { cn } from '$lib/utils.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';
	import { moneyToNumber, type Money } from '$lib/types/money.js';

	let {
		totalValue,
		costBasis = null,
		profitLoss = null,
		returnPercent = null,
		currency = 'CAD',
		showTooltip = true,
		testIdPrefix = undefined,
		class: className = ''
	}: {
		totalValue: number | Money;
		costBasis?: number | Money | null;
		profitLoss?: number | null;
		returnPercent?: number | null;
		currency?: string;
		showTooltip?: boolean;
		testIdPrefix?: string;
		class?: string;
	} = $props();

	const val = $derived(typeof totalValue === 'number' ? totalValue : moneyToNumber(totalValue));

	const cost = $derived(
		costBasis == null
			? profitLoss != null
				? val - profitLoss
				: null
			: typeof costBasis === 'number'
				? costBasis
				: moneyToNumber(costBasis)
	);

	const effectiveCurrency = $derived(
		currency ??
			(typeof totalValue === 'object' &&
			totalValue &&
			'currencyCode' in totalValue &&
			totalValue.currencyCode
				? totalValue.currencyCode
				: 'CAD')
	);

	const effectiveProfitLoss = $derived(
		profitLoss != null ? profitLoss : cost != null ? val - cost : null
	);

	const effectiveReturnPercent = $derived(
		returnPercent != null
			? returnPercent
			: effectiveProfitLoss != null && cost != null && cost !== 0
				? (effectiveProfitLoss / cost) * 100
				: null
	);

	function formatCurrency(amount: number, curr: string): string {
		try {
			return new Intl.NumberFormat('en-CA', {
				style: 'currency',
				currency: curr
			}).format(amount);
		} catch {
			return `${amount >= 0 ? '' : '-'}$${Math.abs(amount).toFixed(2)}`;
		}
	}

	function formatPercent(value: number): string {
		return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
	}

	const isPositive = $derived(
		effectiveProfitLoss != null
			? effectiveProfitLoss >= 0
			: effectiveReturnPercent != null
				? effectiveReturnPercent >= 0
				: true
	);

	const plColorClass = $derived(
		effectiveProfitLoss == null && effectiveReturnPercent == null
			? 'text-muted-foreground'
			: isPositive
				? 'text-emerald-600 dark:text-emerald-400'
				: 'text-rose-600 dark:text-rose-400'
	);

	const formattedTotalValue = $derived(formatCurrency(val, effectiveCurrency));
	const formattedCostBasis = $derived(
		cost != null ? formatCurrency(cost, effectiveCurrency) : null
	);
	const formattedProfitLoss = $derived(
		effectiveProfitLoss != null
			? `${effectiveProfitLoss >= 0 ? '+' : ''}${formatCurrency(effectiveProfitLoss, effectiveCurrency)}`
			: null
	);
	const formattedReturnPercent = $derived(
		effectiveReturnPercent != null ? formatPercent(effectiveReturnPercent) : null
	);
</script>

{#snippet totalButton(triggerProps: Record<string, unknown> = {})}
	<Button
		{...triggerProps}
		variant="outline"
		class="h-8 gap-1.5 px-2.5 font-medium tabular-nums"
		data-testid={testIdPrefix ? `${testIdPrefix}-total-value` : 'total-value-btn'}
	>
		<span>{formattedTotalValue}</span>
	</Button>
{/snippet}

{#snippet profitLossButton(triggerProps: Record<string, unknown> = {})}
	<Button
		{...triggerProps}
		variant="outline"
		class="h-8 gap-1.5 px-2.5 font-medium tabular-nums"
		data-testid={testIdPrefix ? `${testIdPrefix}-profit-loss` : 'profit-loss-btn'}
	>
		{#if formattedReturnPercent}
			<span
				class={cn('font-semibold', plColorClass)}
				data-testid={testIdPrefix ? `${testIdPrefix}-return-percent` : undefined}
			>
				{formattedReturnPercent}
			</span>
		{/if}
		{#if formattedProfitLoss}
			<span
				class={cn(formattedReturnPercent ? 'text-xs font-normal' : 'font-semibold', plColorClass)}
				data-testid={testIdPrefix ? `${testIdPrefix}-profit-loss-value` : undefined}
			>
				{formattedProfitLoss}
			</span>
		{/if}
		{#if !formattedReturnPercent && !formattedProfitLoss}
			<span class="text-xs text-muted-foreground">—</span>
		{/if}
	</Button>
{/snippet}

<div class={cn('inline-flex items-center gap-1.5', className)}>
	{#if showTooltip}
		<Tooltip.Provider>
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props: triggerProps })}
						{@render totalButton(triggerProps)}
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content>
					<p>Total value: {formattedTotalValue}</p>
					{#if formattedCostBasis}
						<p>Total cost: {formattedCostBasis}</p>
					{/if}
					{#if formattedProfitLoss}
						<p>Profit/Loss: {formattedProfitLoss}</p>
					{/if}
				</Tooltip.Content>
			</Tooltip.Root>

			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props: triggerProps })}
						{@render profitLossButton(triggerProps)}
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content>
					{#if formattedProfitLoss}
						<p>
							Profit/Loss: {formattedProfitLoss}{formattedReturnPercent
								? ` (${formattedReturnPercent})`
								: ''}
						</p>
					{/if}
					{#if formattedCostBasis}
						<p>Total cost: {formattedCostBasis}</p>
					{/if}
					<p>Total value: {formattedTotalValue}</p>
				</Tooltip.Content>
			</Tooltip.Root>
		</Tooltip.Provider>
	{:else}
		{@render totalButton()}
		{@render profitLossButton()}
	{/if}
</div>
