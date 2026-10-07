<script lang="ts">
	import PageHeader from '$lib/components/layout/app-header.svelte';
	import HoldingsTable from '$lib/components/holdings/holdings-table.svelte';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import TotalProfitLossButtons from '$lib/components/total-profit-loss-buttons.svelte';
	import Settings2 from '@lucide/svelte/icons/settings-2';
	import Check from '@lucide/svelte/icons/check';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { HoldingsService } from '$lib/components/holdings/holdingsService.svelte';
	import { redirectOn401 } from '$lib/api/async-data';
	import { saveHoldingsTableConfig } from '$lib/components/holdings/holdings-table-prefs';
	import { saveHoldingsGroupMode } from '$lib/components/holdings/holdings-group-prefs';
	import { getUserPreferencesService } from '$lib/api/userPreferencesService';
	import { untrack } from 'svelte';
	import {
		aggregateAccountTotals,
		type AccountTotalsInput
	} from '$lib/utils/finance/account-totals';
	import {
		HOLDINGS_TABLE_COLUMNS,
		HOLDINGS_TABLE_STICKY_COLUMN_ID,
		normalizeHoldingsTableConfig,
		toggleColumnVisibility,
		type HoldingsTableColumnId,
		type HoldingsTableConfig
	} from '$lib/components/holdings/holdings-table-columns';
	import type { HoldingsGroupMode } from '$lib/utils/finance/holdings-group';
	import type { Account } from '$lib/types/account';

	let { data } = $props();

	// The page owns its service instance (SSR "no global instances" rule) and seeds
	// group mode from the server load: toggling grouping never triggers a refetch.
	const service = new HoldingsService();
	service.setGroupBy(data.group_mode);

	// Accounts backing the current filter: "all" covers every account, a portfolio
	// its members, and an account filter the single selected account. Their server
	// totals (not the loaded rows) drive the header.
	const filteredAccounts = $derived.by<Account[]>(() => {
		const filter = service.filter;
		if (filter.type === 'portfolio') {
			const portfolio = data.portfolios?.find((p) => p.id === filter.portfolioId);
			return portfolio?.accounts ?? [];
		}
		if (filter.type === 'account') {
			return (data.accounts ?? []).filter((a) => a.id === filter.accountId);
		}
		return data.accounts ?? [];
	});

	// Synchronize filter from data.portfolio_id or data.account_id
	$effect(() => {
		if (data.portfolio_id) {
			const portfolio = data.portfolios?.find((p) => p.id === data.portfolio_id);
			const accountIds = portfolio ? portfolio.accounts.map((a) => a.id) : [];
			service.filterByPortfolio(data.portfolio_id, accountIds);
		} else if (data.account_id) {
			service.filterByAccount(data.account_id);
		} else {
			service.clearFilter();
		}
	});

	// Holdings rows are fetched after navigation so the shell renders instantly.
	// `$effect` never runs during SSR, so this mount-time trigger stays browser-only
	// and fires exactly once; the sequential pagination waterfall lives in the service.
	$effect(() => {
		void (async () => {
			const loadError = await service.load();

			if (loadError !== null) {
				await redirectOn401(loadError);
			}
		})();
	});

	// Account performance totals are a second post-navigation wave: they follow the
	// visible accounts and reload on filter changes. `untrack` keeps the cache writes
	// inside the service from becoming dependencies of this effect.
	$effect(() => {
		const accountIds = filteredAccounts.map((account) => account.id);
		void untrack(() => service.loadAccountTotals(accountIds));
	});

	const activePortfolio = $derived(
		service.filter.type === 'portfolio'
			? data.portfolios?.find(
					(p) => p.id === (service.filter as { portfolioId: string }).portfolioId
				)
			: null
	);

	const activeAccount = $derived(
		service.filter.type === 'account'
			? data.accounts?.find((a) => a.id === (service.filter as { accountId: string }).accountId)
			: null
	);

	const assignedPortfolio = $derived(
		activeAccount
			? data.portfolios?.find((p) => p.accounts.some((a) => a.id === activeAccount.id))
			: null
	);

	const emptyMessage = $derived(
		service.filter.type !== 'all' && service.allRows.length > 0 && service.rows.length === 0
			? 'No holdings match the selected filter.'
			: 'No holdings yet. Import an account to see your holdings here.'
	);

	function handleSelectFilter(type: 'all' | 'portfolio' | 'account', id?: string) {
		if (type === 'portfolio' && id) {
			const portfolio = data.portfolios?.find((p) => p.id === id);
			const accountIds = portfolio ? portfolio.accounts.map((a) => a.id) : [];
			service.filterByPortfolio(id, accountIds);
			void goto(resolve(`/holdings?portfolio_id=${id}` as unknown as '/'), {
				replaceState: true,
				noScroll: true,
				keepFocus: true
			});
		} else if (type === 'account' && id) {
			service.filterByAccount(id);
			void goto(resolve(`/holdings?account_id=${id}` as unknown as '/'), {
				replaceState: true,
				noScroll: true,
				keepFocus: true
			});
		} else {
			service.clearFilter();
			void goto(resolve('/holdings'), {
				replaceState: true,
				noScroll: true,
				keepFocus: true
			});
		}
	}

	const prefsService = getUserPreferencesService();

	let tableConfig = $state<HoldingsTableConfig>(
		normalizeHoldingsTableConfig(data.holdings_table_config)
	);

	let persistError = $state<string | null>(null);
	const errorMessage = $derived(persistError ?? service.errorMessage);

	// Never sum across currencies: the backend converts each account into its own
	// currency, so totals are bucketed per currency from the accounts' server totals.
	const currencyTotals = $derived.by(() => {
		const inputs: AccountTotalsInput[] = [];

		for (const account of filteredAccounts) {
			const totals = service.accountTotals[account.id];
			if (totals) {
				inputs.push({ accountId: account.id, currency: account.currency, totals });
			}
		}

		return aggregateAccountTotals(inputs);
	});

	function persist(promise: Promise<void>, fallbackMessage: string) {
		persistError = null;
		promise.catch((err) => {
			persistError = err instanceof Error ? err.message : fallbackMessage;
		});
	}

	function handleGroupToggle(checked: boolean | 'indeterminate') {
		const mode: HoldingsGroupMode = checked === true ? 'stock' : 'none';
		service.setGroupBy(mode);
		persist(saveHoldingsGroupMode(prefsService, mode), 'Failed to save group preference');
	}

	function handleToggleColumn(columnId: HoldingsTableColumnId) {
		const nextConfig = toggleColumnVisibility(tableConfig, columnId);
		tableConfig = nextConfig;
		persist(saveHoldingsTableConfig(prefsService, nextConfig), 'Failed to save column preferences');
	}

	function handleConfigChange(nextConfig: HoldingsTableConfig) {
		tableConfig = nextConfig;
		persist(saveHoldingsTableConfig(prefsService, nextConfig), 'Failed to save column preferences');
	}
</script>

<svelte:head>
	<title>Holdings</title>
</svelte:head>

<!-- Bound to the viewport so `main` owns the scroll: the page header stays put
     while the (long) holdings table scrolls underneath it. -->
<div class="flex h-svh max-h-svh min-h-0 flex-1 flex-col overflow-hidden bg-background">
	<PageHeader
		subtitle={service.filter.type === 'all' ? 'All holdings across your accounts' : undefined}
	>
		{#snippet titleSlot()}
			{#if service.filter.type === 'all'}
				<h2 class="text-lg font-semibold">Holdings</h2>
			{:else}
				<nav aria-label="Breadcrumb" class="flex items-center gap-1.5">
					<button
						type="button"
						class="cursor-pointer text-lg font-semibold text-muted-foreground transition-colors hover:text-primary"
						onclick={() => handleSelectFilter('all')}
						data-testid="breadcrumb-holdings"
					>
						Holdings
					</button>
					<ChevronRight class="h-4 w-4 shrink-0 text-muted-foreground" />

					{#if (service.filter.type === 'portfolio' && activePortfolio) || assignedPortfolio}
						{@const port =
							service.filter.type === 'portfolio' ? activePortfolio : assignedPortfolio}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								{#snippet child({ props })}
									<button
										{...props}
										type="button"
										data-testid="breadcrumb-portfolio-trigger"
										class="flex cursor-pointer items-center gap-1 text-lg font-semibold transition-colors hover:text-primary {service
											.filter.type === 'account'
											? 'text-muted-foreground'
											: ''}"
									>
										<span>{port?.name ?? 'Portfolio'}</span>
										<ChevronDown class="h-4 w-4 opacity-50" />
									</button>
								{/snippet}
							</DropdownMenu.Trigger>
							<DropdownMenu.Content align="start" class="w-48">
								{#if data.portfolios && data.portfolios.length > 0}
									{#each data.portfolios as portfolio (portfolio.id)}
										<DropdownMenu.Item
											data-testid={`breadcrumb-portfolio-${portfolio.id}`}
											class="flex items-center justify-between"
											onSelect={() => handleSelectFilter('portfolio', portfolio.id)}
										>
											<span class="truncate">{portfolio.name}</span>
											{#if port?.id === portfolio.id}
												<Check size={14} />
											{/if}
										</DropdownMenu.Item>
									{/each}
								{/if}
							</DropdownMenu.Content>
						</DropdownMenu.Root>

						{#if service.filter.type === 'account' && activeAccount}
							<ChevronRight class="h-4 w-4 shrink-0 text-muted-foreground" />
						{/if}
					{/if}

					{#if service.filter.type === 'account' && activeAccount}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								{#snippet child({ props })}
									<button
										{...props}
										type="button"
										data-testid="breadcrumb-account-trigger"
										class="flex cursor-pointer items-center gap-1 text-lg font-semibold transition-colors hover:text-primary"
									>
										<span>{activeAccount.name}</span>
										<ChevronDown class="h-4 w-4 opacity-50" />
									</button>
								{/snippet}
							</DropdownMenu.Trigger>
							<DropdownMenu.Content align="start" class="w-48">
								{#if data.accounts && data.accounts.length > 0}
									{#each data.accounts as account (account.id)}
										<DropdownMenu.Item
											data-testid={`breadcrumb-account-${account.id}`}
											class="flex items-center justify-between"
											onSelect={() => handleSelectFilter('account', account.id)}
										>
											<span class="truncate">{account.name}</span>
											{#if activeAccount.id === account.id}
												<Check size={14} />
											{/if}
										</DropdownMenu.Item>
									{/each}
								{/if}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				</nav>
			{/if}
		{/snippet}
		{#snippet actions()}
			<div class="flex items-center gap-6">
				{#each currencyTotals as total (total.currency)}
					<TotalProfitLossButtons
						totalValue={total.totalValue}
						profitLoss={total.profitLoss}
						returnPercent={total.returnPercent}
						currency={total.currency}
						basisLabel={total.basisLabel}
						testIdPrefix={`currency-${total.currency}`}
					/>
				{/each}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Button
								{...props}
								variant="outline"
								size="icon"
								data-testid="display-settings-trigger"
								aria-label="Settings"
								title="Settings"
							>
								<Settings2 class="h-4 w-4" />
							</Button>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="end" class="w-56">
						{#if data.portfolios && data.portfolios.length > 0}
							<DropdownMenu.Label>Portfolios</DropdownMenu.Label>
							{#each data.portfolios as portfolio (portfolio.id)}
								<DropdownMenu.Item
									data-testid={`filter-portfolio-${portfolio.id}`}
									class="flex items-center justify-between"
									onSelect={() => handleSelectFilter('portfolio', portfolio.id)}
								>
									<span class="truncate">{portfolio.name}</span>
									{#if service.filter.type === 'portfolio' && (service.filter as { portfolioId: string }).portfolioId === portfolio.id}
										<Check size={14} />
									{/if}
								</DropdownMenu.Item>
							{/each}
							<DropdownMenu.Separator />
						{/if}
						<DropdownMenu.Label>Accounts</DropdownMenu.Label>
						<DropdownMenu.Item
							data-testid="filter-all"
							class="flex items-center justify-between"
							onSelect={() => handleSelectFilter('all')}
						>
							<span>All accounts</span>
							{#if service.filter.type === 'all'}
								<Check size={14} />
							{/if}
						</DropdownMenu.Item>
						{#if data.accounts && data.accounts.length > 0}
							{#each data.accounts as account (account.id)}
								<DropdownMenu.Item
									data-testid={`filter-account-${account.id}`}
									class="flex items-center justify-between"
									onSelect={() => handleSelectFilter('account', account.id)}
								>
									<span class="truncate">{account.name}</span>
									{#if service.filter.type === 'account' && (service.filter as { accountId: string }).accountId === account.id}
										<Check size={14} />
									{/if}
								</DropdownMenu.Item>
							{/each}
						{/if}
						<DropdownMenu.Separator />
						<DropdownMenu.Label>View options</DropdownMenu.Label>
						<DropdownMenu.CheckboxItem
							data-testid="group-by-stock"
							checked={service.groupBy === 'stock' || service.groupBy === 'company'}
							onCheckedChange={handleGroupToggle}
						>
							Group by stock
						</DropdownMenu.CheckboxItem>
						<DropdownMenu.Separator />
						<DropdownMenu.Label>Visible columns</DropdownMenu.Label>
						{#each HOLDINGS_TABLE_COLUMNS as column (column.id)}
							<DropdownMenu.CheckboxItem
								checked={tableConfig.visible.includes(column.id)}
								disabled={column.id === HOLDINGS_TABLE_STICKY_COLUMN_ID}
								onCheckedChange={() => handleToggleColumn(column.id)}
								data-testid={`column-toggle-${column.id}`}
							>
								{column.label}
							</DropdownMenu.CheckboxItem>
						{/each}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		{/snippet}
	</PageHeader>

	{#if errorMessage}
		<div class="px-4 pt-3">
			<Alert.Root variant="destructive" data-testid="holdings-error">
				<Alert.Description>{errorMessage}</Alert.Description>
			</Alert.Root>
		</div>
	{/if}

	<main class="flex-1 overflow-auto">
		<HoldingsTable
			holdings={service.rows}
			groupBy={service.groupBy === 'stock' || service.groupBy === 'company' ? 'stock' : null}
			isLoading={service.isLoading}
			{tableConfig}
			onConfigChange={handleConfigChange}
			onAccountClick={(accountId) => handleSelectFilter('account', accountId)}
			onValuationChange={(secId, val) => {
				service.valuations[secId] = val;
			}}
			elliottWaves={data.elliott_waves}
			valuations={service.valuations}
			{emptyMessage}
		/>
	</main>
</div>
