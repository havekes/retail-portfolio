<script lang="ts">
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import { formatDate } from '$lib/utils/date';
	import { resolve } from '$app/paths';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Portfolios</title>
</svelte:head>

<div class="flex h-full flex-col overflow-hidden bg-background">
	<PageHeader title="Portfolios" subtitle="Overview of your portfolios and accounts" />

	<main class="flex-1 overflow-auto p-6">
		{#if !data.portfolios || data.portfolios.length === 0}
			<div
				class="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed p-8 text-center"
				data-testid="empty-state"
			>
				<p class="text-sm font-medium">You don't have any portfolios yet</p>
			</div>
		{:else}
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
				{#each data.portfolios as portfolio (portfolio.id)}
					<a
						href={resolve(('/holdings?portfolio_id=' + portfolio.id) as unknown as '/')}
						data-testid={`portfolio-card-${portfolio.id}`}
						class="block rounded-xl transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					>
						<Card.Root class="h-full transition-colors hover:border-primary/50">
							<Card.Header>
								<Card.Title class="text-lg font-semibold">{portfolio.name}</Card.Title>
								<Card.Description>
									{portfolio.accounts.length}
									{portfolio.accounts.length === 1 ? 'account' : 'accounts'}
								</Card.Description>
							</Card.Header>
							<Card.Content>
								{#if portfolio.created_at}
									<p class="text-xs text-muted-foreground">
										Created {formatDate(portfolio.created_at)}
									</p>
								{/if}
							</Card.Content>
						</Card.Root>
					</a>
				{/each}
			</div>
		{/if}
	</main>
</div>
