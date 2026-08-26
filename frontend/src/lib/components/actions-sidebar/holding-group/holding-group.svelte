<script lang="ts">
	import { untrack } from 'svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import GroupTitle from '../group-title.svelte';
	import Skeleton from '@/components/ui/skeleton/skeleton.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import { accountService, type AccountHoldingRead } from '@/api/accountService';
	import { accountClient } from '$lib/api/accountClient';
	import { blendedAverageCost } from '@/utils/finance/average-cost';
	import { resolve } from '$app/paths';
	import Maximize2 from '@lucide/svelte/icons/maximize-2';
	import HoldingsModal from './holdings-modal.svelte';
	import { ModalState } from '$lib/utils/modal-state.svelte';
	import type { SecuritySchema } from '@/api/marketService';
	import type { Candle } from '@/utils/finance/candle';
	import { moneyToNumber } from '$lib/types/money';

	let {
		securityId,
		security,
		candles = [],
		expanded = $bindable(true)
	} = $props<{
		securityId?: string;
		security?: SecuritySchema | { id?: string; symbol?: string; name?: string; currency?: string };
		candles?: Candle[];
		expanded?: boolean;
	}>();

	const effectiveSecurityId = $derived(securityId ?? security?.id);

	let holdings = $state<AccountHoldingRead[]>([]);
	let portfolioPercentage = $state<number | null>(null);
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const holdingsModalState = new ModalState<SecuritySchema>();

	const handleExpandModal = () => {
		holdingsModalState.open(security as SecuritySchema);
	};

	const fetchHoldings = async () => {
		if (!effectiveSecurityId) return;
		if (holdings.length === 0) {
			isLoading = true;
		}
		error = null;
		try {
			const [holdingsRes, accounts] = await Promise.all([
				accountService.getHoldings(effectiveSecurityId),
				accountClient.getAccounts()
			]);
			holdings = holdingsRes.items;

			const totalsList = await Promise.all(
				accounts.map((acc) => accountClient.getAccountTotals(acc.id))
			);

			let totalPortfolioValue = 0;
			for (const totals of totalsList) {
				totalPortfolioValue += moneyToNumber(totals?.value);
			}

			const totalSecurityValue = holdings.reduce((sum, h) => sum + (h.total_value ?? 0), 0);

			if (totalPortfolioValue > 0) {
				portfolioPercentage = (totalSecurityValue / totalPortfolioValue) * 100;
			} else {
				portfolioPercentage = 0;
			}
		} catch (err) {
			console.error('Failed to fetch holdings:', err);
			error = 'Failed to load holdings';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (expanded && effectiveSecurityId) {
			untrack(() => {
				fetchHoldings();
			});
		}
	});

	const handleExpandToggle = () => {
		expanded = !expanded;
	};
</script>

<HoldingsModal
	modalState={holdingsModalState}
	securityId={effectiveSecurityId}
	{security}
	{holdings}
	{candles}
/>

<Sidebar.Group>
	<GroupTitle
		{expanded}
		onToggle={handleExpandToggle}
		actionIcon={Maximize2}
		actionTitle="Expand holdings breakdown"
		onAction={handleExpandModal}
	>
		Your Holdings
	</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			{#if isLoading}
				<div class="space-y-2 py-2">
					<Skeleton class="h-8 w-full rounded-md bg-background" />
					<Skeleton class="h-8 w-full rounded-md bg-background" />
				</div>
			{:else if error}
				<div class="py-2">
					<SidebarError message={error} onretry={fetchHoldings} />
				</div>
			{:else if holdings.length === 0}
				<div class="p-2 text-sm text-muted-foreground">
					You don't hold any shares of this security.
				</div>
			{:else}
				<div class="space-y-1 py-2 text-sm">
					<div class="mb-2 flex items-center justify-between rounded-md bg-muted/40 px-2 py-1.5">
						<div class="flex flex-col">
							<span class="text-xs text-muted-foreground">Average</span>
							<span class="font-semibold text-foreground">
								{new Intl.NumberFormat('en-US', {
									style: 'currency',
									currency: holdings[0]?.currency ?? security?.currency ?? 'USD'
								}).format(blendedAverageCost(holdings))}
							</span>
						</div>
						<div class="flex flex-col text-right">
							<span class="text-xs text-muted-foreground">% of Portfolio</span>
							<span class="font-semibold text-foreground">
								{portfolioPercentage !== null ? `${portfolioPercentage.toFixed(2)}%` : '0.00%'}
							</span>
						</div>
					</div>

					{#each holdings as holding (holding.account_id)}
						<a
							href={resolve(`/accounts/${holding.account_id}`)}
							class="flex flex-col rounded-md px-2 py-1.5 no-underline hover:bg-muted/50"
						>
							<div class="flex justify-between">
								<span class="font-medium text-foreground">{holding.account_name}</span>
								<span class="text-foreground">
									{new Intl.NumberFormat('en-US', {
										style: 'currency',
										currency: holding.currency
									}).format(holding.total_value)}
								</span>
							</div>
							<div class="text-xs text-muted-foreground">
								{holding.quantity} shares · Avg
								{new Intl.NumberFormat('en-US', {
									style: 'currency',
									currency: holding.currency
								}).format(holding.average_cost ?? 0)}
							</div>
						</a>
					{/each}
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>
