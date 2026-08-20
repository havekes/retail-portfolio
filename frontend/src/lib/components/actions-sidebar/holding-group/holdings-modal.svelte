<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import Skeleton from '$lib/components/ui/skeleton/skeleton.svelte';
	import Sparkline from '$lib/components/charts/sparkline.svelte';
	import { accountService, type AccountHoldingRead } from '$lib/api/accountService';
	import { userPreferencesService } from '$lib/api/userPreferencesService';
	import type { SecuritySchema } from '$lib/api/marketService';
	import type { Candle } from '$lib/utils/finance/candle';
	import {
		type HoldingsPeriod,
		getBenchmarkPrice,
		calculateHoldingGain,
		filterCandlesForPeriod
	} from '$lib/utils/finance/holdings-metrics';
	import { blendedAverageCost } from '$lib/utils/finance/average-cost';
	import type { ModalState } from '$lib/utils/modal-state.svelte';
	import { resolve } from '$app/paths';

	const PERIODS: HoldingsPeriod[] = ['1D', '1W', '1M', '1Y', 'YTD', 'ALL'];

	let {
		modalState,
		open = $bindable(false),
		securityId,
		security,
		holdings: initialHoldings,
		candles = [],
		currentPrice: propCurrentPrice
	} = $props<{
		modalState?: ModalState<SecuritySchema> | ModalState<unknown>;
		open?: boolean;
		securityId?: string;
		security?: SecuritySchema | { id?: string; symbol?: string; name?: string; currency?: string };
		holdings?: AccountHoldingRead[];
		candles?: Candle[];
		currentPrice?: number;
	}>();

	let isOpen = $state(false);
	let selectedPeriod = $state<HoldingsPeriod>('ALL');
	let fetchedHoldings = $state<AccountHoldingRead[]>([]);
	let isLoading = $state(false);
	let error = $state<string | null>(null);
	let hasUserChangedPeriod = false;

	// Sync open state with modalState or open prop
	$effect(() => {
		if (modalState !== undefined) {
			isOpen = modalState.isOpen;
		} else {
			isOpen = open;
		}
	});

	const effectiveSecurity = $derived(
		security ??
			(modalState?.data as
				| (SecuritySchema & { id?: string; symbol?: string; name?: string; currency?: string })
				| undefined)
	);

	const effectiveSecurityId = $derived(securityId ?? effectiveSecurity?.id);

	const securitySymbol = $derived(effectiveSecurity?.symbol);
	const securityName = $derived(effectiveSecurity?.name);
	const securitySubtitle = $derived.by(() => {
		if (securitySymbol && securityName) {
			return `${securitySymbol} · ${securityName}`;
		}
		return securitySymbol || securityName || '';
	});

	const effectiveHoldings = $derived<AccountHoldingRead[]>(initialHoldings ?? fetchedHoldings);

	const resolvedCurrentPrice = $derived.by(() => {
		if (typeof propCurrentPrice === 'number' && !isNaN(propCurrentPrice) && propCurrentPrice > 0) {
			return propCurrentPrice;
		}
		if (candles && candles.length > 0) {
			const lastCandle = candles[candles.length - 1];
			if (typeof lastCandle.close === 'number' && !isNaN(lastCandle.close)) {
				return lastCandle.close;
			}
		}
		if (effectiveHoldings.length > 0 && effectiveHoldings[0].quantity > 0) {
			return effectiveHoldings[0].total_value / effectiveHoldings[0].quantity;
		}
		return 0;
	});

	const sparklineCandles = $derived(filterCandlesForPeriod(candles, selectedPeriod));

	const loadPreferences = async () => {
		try {
			const prefs = await userPreferencesService.getPreferences();
			if (hasUserChangedPeriod) return;
			if (prefs?.holdings_period && PERIODS.includes(prefs.holdings_period as HoldingsPeriod)) {
				selectedPeriod = prefs.holdings_period as HoldingsPeriod;
			} else {
				selectedPeriod = 'ALL';
			}
		} catch (err) {
			console.error('Failed to load holdings period preference:', err);
			if (!hasUserChangedPeriod) {
				selectedPeriod = 'ALL';
			}
		}
	};

	const fetchHoldings = async () => {
		if (initialHoldings !== undefined) return;
		if (!effectiveSecurityId) return;
		isLoading = true;
		error = null;
		try {
			const res = await accountService.getHoldings(effectiveSecurityId);
			fetchedHoldings = res.items ?? [];
		} catch (err) {
			console.error('Failed to fetch holdings:', err);
			error = err instanceof Error ? err.message : 'Failed to load holdings';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (isOpen) {
			hasUserChangedPeriod = false;
			loadPreferences();
			if (initialHoldings === undefined && effectiveSecurityId) {
				fetchHoldings();
			}
		}
	});

	function handleOpenChange(val: boolean) {
		isOpen = val;
		open = val;
		if (modalState) {
			if (val) {
				modalState.isOpen = true;
			} else {
				modalState.close();
			}
		}
	}

	function handlePeriodSelect(period: HoldingsPeriod) {
		hasUserChangedPeriod = true;
		selectedPeriod = period;
		userPreferencesService.patchPreferences({ holdings_period: period }).catch((err) => {
			console.error('Failed to save holdings period preference:', err);
		});
	}

	function formatCurrency(val: number, currency: string = 'USD'): string {
		return new Intl.NumberFormat('en-US', {
			style: 'currency',
			currency: currency || 'USD'
		}).format(val);
	}

	function formatShares(val: number): string {
		return val.toLocaleString('en-US', {
			minimumFractionDigits: 0,
			maximumFractionDigits: 4
		});
	}

	function getHoldingMetrics(
		holding: AccountHoldingRead,
		period: HoldingsPeriod,
		currentPrice: number,
		candleData: Candle[]
	) {
		const benchmarkPrice = getBenchmarkPrice(candleData, period, holding.average_cost);
		const effectiveBenchmark = benchmarkPrice ?? holding.average_cost ?? currentPrice;
		const gain = calculateHoldingGain(currentPrice, effectiveBenchmark, holding.quantity);
		return {
			benchmarkPrice: effectiveBenchmark,
			gain
		};
	}

	// Footer aggregate calculations
	const totalShares = $derived(
		effectiveHoldings.reduce((sum: number, h: AccountHoldingRead) => sum + h.quantity, 0)
	);

	const portfolioAvgPrice = $derived(blendedAverageCost(effectiveHoldings));

	const totalValue = $derived(
		effectiveHoldings.reduce((sum: number, h: AccountHoldingRead) => sum + h.total_value, 0)
	);

	const primaryCurrency = $derived(
		effectiveHoldings[0]?.currency ?? effectiveSecurity?.currency ?? 'USD'
	);

	const totalGainSummary = $derived.by(() => {
		if (effectiveHoldings.length === 0) {
			return { totalGainAmount: 0, totalGainPercent: 0 };
		}
		let sumGain = 0;
		let sumBenchmarkValue = 0;
		for (const h of effectiveHoldings) {
			const { benchmarkPrice, gain } = getHoldingMetrics(
				h,
				selectedPeriod,
				resolvedCurrentPrice,
				candles
			);
			sumGain += gain.gainAmount;
			sumBenchmarkValue += benchmarkPrice * h.quantity;
		}
		const totalGainPercent = sumBenchmarkValue !== 0 ? (sumGain / sumBenchmarkValue) * 100 : 0;
		return {
			totalGainAmount: sumGain,
			totalGainPercent
		};
	});
</script>

<Dialog.Root bind:open={isOpen} onOpenChange={handleOpenChange}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="w-full max-w-4xl sm:max-w-5xl">
			<Dialog.Header class="space-y-3 pb-2">
				<div class="flex flex-col gap-3 pr-6 sm:flex-row sm:items-center sm:justify-between">
					<div>
						<Dialog.Title class="text-xl font-semibold">Holdings Breakdown</Dialog.Title>
						<Dialog.Description class="text-sm text-muted-foreground">
							{#if securitySubtitle}
								{securitySubtitle}
							{:else}
								Detailed breakdown of your holdings across all accounts
							{/if}
						</Dialog.Description>
					</div>
					<div
						class="flex items-center gap-1 self-start rounded-lg border bg-muted/30 p-1 sm:self-auto"
						role="group"
						aria-label="Holdings timeframe"
					>
						{#each PERIODS as period (period)}
							<button
								type="button"
								onclick={() => handlePeriodSelect(period)}
								class="rounded px-2.5 py-1 text-xs font-medium transition-colors {selectedPeriod ===
								period
									? 'bg-primary text-primary-foreground shadow-sm'
									: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
								aria-pressed={selectedPeriod === period}
							>
								{period}
							</button>
						{/each}
					</div>
				</div>
			</Dialog.Header>

			{#if isLoading}
				<div class="space-y-3 py-6" data-testid="holdings-loading-skeleton">
					<Skeleton class="h-10 w-full rounded-md" />
					<Skeleton class="h-10 w-full rounded-md" />
					<Skeleton class="h-10 w-full rounded-md" />
				</div>
			{:else if error}
				<div
					class="flex flex-col items-center justify-center gap-3 py-8 text-center"
					data-testid="holdings-error-state"
				>
					<p class="text-sm text-destructive">{error}</p>
					<Button variant="outline" size="sm" onclick={fetchHoldings}>Retry</Button>
				</div>
			{:else if effectiveHoldings.length === 0}
				<div
					class="flex flex-col items-center justify-center py-12 text-center text-muted-foreground"
					data-testid="holdings-empty-state"
				>
					<p class="text-sm">No holdings found for this security.</p>
				</div>
			{:else}
				<div class="overflow-x-auto rounded-md border">
					<Table.Root>
						<Table.Header class="bg-muted/40">
							<Table.Row>
								<Table.Head class="text-left font-semibold">Account</Table.Head>
								<Table.Head class="text-right font-semibold">Shares</Table.Head>
								<Table.Head class="text-right font-semibold">Avg Price</Table.Head>
								<Table.Head class="text-right font-semibold">Total Value</Table.Head>
								<Table.Head class="text-right font-semibold">% of Account</Table.Head>
								<Table.Head class="text-right font-semibold">Period Gain</Table.Head>
								<Table.Head class="w-28 text-center font-semibold">Trend</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each effectiveHoldings as holding (holding.account_id)}
								{@const { gain } = getHoldingMetrics(
									holding,
									selectedPeriod,
									resolvedCurrentPrice,
									candles
								)}
								<Table.Row class="hover:bg-muted/30">
									<Table.Cell class="text-left font-medium">
										<a
											href={resolve(`/accounts/${holding.account_id}`)}
											class="text-foreground hover:underline"
										>
											{holding.account_name}
										</a>
									</Table.Cell>
									<Table.Cell class="text-right tabular-nums">
										{formatShares(holding.quantity)}
									</Table.Cell>
									<Table.Cell class="text-right tabular-nums">
										{formatCurrency(holding.average_cost ?? 0, holding.currency)}
									</Table.Cell>
									<Table.Cell class="text-right font-medium tabular-nums">
										{formatCurrency(holding.total_value, holding.currency)}
									</Table.Cell>
									<Table.Cell class="text-right tabular-nums">
										{holding.account_percentage != null
											? `${holding.account_percentage.toFixed(2)}%`
											: '-'}
									</Table.Cell>
									<Table.Cell class="text-right tabular-nums">
										<div class="flex flex-col items-end leading-tight">
											<span
												class={gain.gainAmount >= 0
													? 'text-emerald-600 dark:text-emerald-400'
													: 'text-rose-600 dark:text-rose-400'}
											>
												{gain.gainAmount >= 0 ? '+' : ''}{formatCurrency(
													gain.gainAmount,
													holding.currency
												)}
											</span>
											<span
												class="text-xs {gain.gainAmount >= 0
													? 'text-emerald-600/80 dark:text-emerald-400/80'
													: 'text-rose-600/80 dark:text-rose-400/80'}"
											>
												{gain.gainAmount >= 0 ? '+' : ''}{gain.gainPercent.toFixed(2)}%
											</span>
										</div>
									</Table.Cell>
									<Table.Cell class="text-center">
										<div class="flex items-center justify-center">
											<Sparkline
												data={sparklineCandles}
												isPositive={gain.gainAmount >= 0}
												width={96}
												height={28}
											/>
										</div>
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
						<Table.Footer>
							<Table.Row class="bg-muted/50 font-semibold">
								<Table.Cell class="text-left font-semibold">Total</Table.Cell>
								<Table.Cell class="text-right tabular-nums">
									{formatShares(totalShares)}
								</Table.Cell>
								<Table.Cell class="text-right tabular-nums">
									{formatCurrency(portfolioAvgPrice, primaryCurrency)}
								</Table.Cell>
								<Table.Cell class="text-right font-semibold tabular-nums">
									{formatCurrency(totalValue, primaryCurrency)}
								</Table.Cell>
								<Table.Cell class="text-right text-muted-foreground tabular-nums">-</Table.Cell>
								<Table.Cell class="text-right tabular-nums">
									<div class="flex flex-col items-end leading-tight">
										<span
											class={totalGainSummary.totalGainAmount >= 0
												? 'text-emerald-600 dark:text-emerald-400'
												: 'text-rose-600 dark:text-rose-400'}
										>
											{totalGainSummary.totalGainAmount >= 0 ? '+' : ''}{formatCurrency(
												totalGainSummary.totalGainAmount,
												primaryCurrency
											)}
										</span>
										<span
											class="text-xs {totalGainSummary.totalGainAmount >= 0
												? 'text-emerald-600/80 dark:text-emerald-400/80'
												: 'text-rose-600/80 dark:text-rose-400/80'}"
										>
											{totalGainSummary.totalGainAmount >= 0
												? '+'
												: ''}{totalGainSummary.totalGainPercent.toFixed(2)}%
										</span>
									</div>
								</Table.Cell>
								<Table.Cell></Table.Cell>
							</Table.Row>
						</Table.Footer>
					</Table.Root>
				</div>
			{/if}

			<Dialog.Footer class="pt-2 sm:justify-end">
				<Button variant="outline" onclick={() => handleOpenChange(false)}>Close</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
