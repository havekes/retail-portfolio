<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import GroupTitle from '../group-title.svelte';
	import Skeleton from '@/components/ui/skeleton/skeleton.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import { accountService, type AccountHoldingRead } from '@/api/accountService';
	import { resolve } from '$app/paths';

	let { securityId, expanded = $bindable(true) } = $props<{
		securityId: string;
		expanded?: boolean;
	}>();

	let holdings = $state<AccountHoldingRead[]>([]);
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const fetchHoldings = async () => {
		if (!securityId) return;
		isLoading = true;
		error = null;
		try {
			holdings = await accountService.getHoldings(securityId);
		} catch (err) {
			console.error('Failed to fetch holdings:', err);
			error = 'Failed to load holdings';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (expanded && securityId) {
			fetchHoldings();
		}
	});

	const handleExpandToggle = () => {
		expanded = !expanded;
	};
</script>

<Sidebar.Group>
	<GroupTitle {expanded} onToggle={handleExpandToggle}>Your Holdings</GroupTitle>

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
								{holding.quantity} shares
							</div>
						</a>
					{/each}
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>
