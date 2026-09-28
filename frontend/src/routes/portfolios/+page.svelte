<script lang="ts">
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import PortfolioListItem from './portfolio-list-item.svelte';
	import { portfolioClient } from '$lib/api/portfolioClient';
	import type { Portfolio } from '$lib/types/portfolio';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let localPortfolios = $state<Portfolio[] | null>(null);
	const portfolios = $derived(localPortfolios ?? data.portfolios ?? []);

	async function handleRename(portfolioId: string, newName: string) {
		try {
			await portfolioClient.updatePortfolio(portfolioId, { name: newName });
			localPortfolios = portfolios.map((p) => (p.id === portfolioId ? { ...p, name: newName } : p));
		} catch (error) {
			console.error('Failed to rename portfolio:', error);
		}
	}

	async function handleDelete(portfolioId: string) {
		try {
			await portfolioClient.deletePortfolio(portfolioId);
			localPortfolios = portfolios.filter((p) => p.id !== portfolioId);
		} catch (error) {
			console.error('Failed to delete portfolio:', error);
		}
	}
</script>

<svelte:head>
	<title>Portfolios</title>
</svelte:head>

<div class="flex h-full flex-col overflow-hidden bg-background">
	<PageHeader title="Portfolios" subtitle="Overview of your portfolios and accounts" />

	<main class="flex-1 overflow-auto p-6">
		{#if !portfolios || portfolios.length === 0}
			<div
				class="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed p-8 text-center"
				data-testid="empty-state"
			>
				<p class="text-sm font-medium">You don't have any portfolios yet</p>
			</div>
		{:else}
			<div class="space-y-3">
				{#each portfolios as portfolio (portfolio.id)}
					<PortfolioListItem
						{portfolio}
						onRename={(newName) => handleRename(portfolio.id, newName)}
						onDelete={() => handleDelete(portfolio.id)}
					/>
				{/each}
			</div>
		{/if}
	</main>
</div>
