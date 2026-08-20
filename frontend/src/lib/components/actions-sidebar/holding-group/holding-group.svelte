<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import GroupTitle from '../group-title.svelte';
	import Skeleton from '@/components/ui/skeleton/skeleton.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import { accountService, type AccountHoldingRead } from '@/api/accountService';
	import { blendedAverageCost } from '@/utils/finance/average-cost';
	import { resolve } from '$app/paths';
	import Maximize2 from '@lucide/svelte/icons/maximize-2';
	import HoldingsModal from './holdings-modal.svelte';
	import { ModalState } from '$lib/utils/modal-state.svelte';
	import type { SecuritySchema } from '@/api/marketService';
	import type { Candle } from '@/utils/finance/candle';

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
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const holdingsModalState = new ModalState<SecuritySchema>();

	const handleExpandModal = () => {
		holdingsModalState.open(security as SecuritySchema);
	};

	const fetchHoldings = async () => {
		if (!effectiveSecurityId) return;
		isLoading = true;
		error = null;
		try {
			const res = await accountService.getHoldings(effectiveSecurityId);
			holdings = res.items;
		} catch (err) {
			console.error('Failed to fetch holdings:', err);
			error = 'Failed to load holdings';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (expanded && effectiveSecurityId) {
			fetchHoldings();
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
					<div class="mt-1 flex justify-between rounded-md border-t border-border px-2 py-1.5">
						<span class="text-xs text-muted-foreground">Portfolio avg</span>
						<span class="text-xs font-medium text-foreground">
							{new Intl.NumberFormat('en-US', {
								style: 'currency',
								currency: holdings[0]?.currency ?? 'USD'
							}).format(blendedAverageCost(holdings))}
						</span>
					</div>
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>
