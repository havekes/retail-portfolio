import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import Page from './+page.svelte';
import type { AccountTotals, UserHolding, Account } from '$lib/types/account';
import { AccountType, Institution } from '$lib/types/account';
import type { Portfolio } from '$lib/types/portfolio';
import {
	HOLDINGS_TABLE_DEFAULT_CONFIG,
	normalizeHoldingsTableConfig
} from '$lib/components/holdings/holdings-table-columns';
import type { HoldingsGroupMode } from '$lib/utils/finance/holdings-group';
import type { SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$lib/api/accountService', () => ({
	getAccountService: vi.fn()
}));

vi.mock('$lib/api/accountClient', () => ({
	getAccountClient: vi.fn()
}));

vi.mock('$lib/api/marketService', () => ({
	getMarketService: vi.fn()
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	getUserPreferencesService: vi.fn()
}));

vi.mock('$lib/api/valuationClient', () => ({
	valuationClient: {
		setValuation: vi.fn(),
		getValuation: vi.fn()
	}
}));

import { goto } from '$app/navigation';
import { ApiError } from '$lib/api/apiClient';
import { getAccountService, type AccountService } from '$lib/api/accountService';
import { getAccountClient, type AccountClient } from '$lib/api/accountClient';
import { getMarketService, type MarketService } from '$lib/api/marketService';
import {
	getUserPreferencesService,
	type UserPreferencesService
} from '$lib/api/userPreferencesService';
import { valuationClient } from '$lib/api/valuationClient';

const getUserHoldings = vi.fn();
const getValuationsBatch = vi.fn();
const getPreferences = vi.fn();
const patchPreferences = vi.fn();
const getAccountTotals = vi.fn();

function makeTotals(
	value: number,
	profitLoss: number,
	overrides: Partial<AccountTotals> = {}
): AccountTotals {
	return {
		cost: { value: String(value - profitLoss) },
		value: { value: String(value) },
		cash: { value: '0' },
		net_deposits: null,
		profit_loss: { value: String(profitLoss) },
		return_percent: null,
		basis: 'cost',
		...overrides
	};
}

function makeRow(
	overrides: Partial<UserHolding> &
		Pick<UserHolding, 'id' | 'security_id' | 'security_symbol' | 'security_name'>
): UserHolding {
	const merged = {
		quantity: 1,
		average_cost: 100,
		total_value: 100,
		profit_loss: 0,
		currency: 'CAD',
		display_currency: 'CAD',
		security_currency: 'CAD',
		unconverted_total_value: 100,
		converted_average_cost: 100,
		converted_latest_price: 100,
		unconverted_profit_loss: 0,
		latest_price: 100,
		account_id: 'acc-1',
		account_name: 'TFSA',
		...overrides
	};
	return { ...merged, display_total_value: overrides.display_total_value ?? merged.total_value };
}

const aaplTfsa = makeRow({
	id: 'h-aapl-tfsa',
	security_id: 'sec-aapl',
	security_symbol: 'AAPL',
	security_name: 'Apple Inc.',
	quantity: 10,
	total_value: 1000,
	unconverted_total_value: 1000,
	profit_loss: 100,
	unconverted_profit_loss: 100,
	account_id: 'acc-1',
	account_name: 'TFSA'
});

const aaplRrsp = makeRow({
	id: 'h-aapl-rrsp',
	security_id: 'sec-aapl',
	security_symbol: 'AAPL',
	security_name: 'Apple Inc.',
	quantity: 5,
	total_value: 500,
	unconverted_total_value: 500,
	profit_loss: -50,
	unconverted_profit_loss: -50,
	account_id: 'acc-2',
	account_name: 'RRSP'
});

const msftRrsp = makeRow({
	id: 'h-msft-rrsp',
	security_id: 'sec-msft',
	security_symbol: 'MSFT',
	security_name: 'Microsoft Corp.',
	quantity: 2,
	total_value: 400,
	unconverted_total_value: 400,
	profit_loss: 25,
	unconverted_profit_loss: 25,
	account_id: 'acc-2',
	account_name: 'RRSP'
});

const aaplUsd = makeRow({
	id: 'h-aapl-usd',
	security_id: 'sec-aapl',
	security_symbol: 'AAPL',
	security_name: 'Apple Inc.',
	quantity: 1,
	total_value: 200,
	unconverted_total_value: 200,
	profit_loss: 20,
	unconverted_profit_loss: 20,
	currency: 'USD',
	security_currency: 'USD',
	account_id: 'acc-3',
	account_name: 'USD Account'
});

function pageOf(items: UserHolding[], total = items.length) {
	return { items, total, offset: 0, limit: 50 };
}

function makeData(
	overrides: Partial<{
		holdings_table_config: typeof HOLDINGS_TABLE_DEFAULT_CONFIG;
		group_mode: HoldingsGroupMode;
		elliott_waves: Record<string, SecurityElliottWaves> | null;
		portfolios: Portfolio[];
		accounts: Account[];
		portfolio_id: string | null;
		account_id: string | null;
	}> = {}
) {
	return {
		user: { id: 'u1', email: 'test@example.com' },
		sidebar_open: true,
		collapsed_watchlist_ids: [] as string[],
		watchlist_order: null as string[] | null,
		expanded_account_ids: [] as string[],
		holdings_table_config: HOLDINGS_TABLE_DEFAULT_CONFIG,
		group_mode: 'none' as HoldingsGroupMode,
		elliott_waves: null as Record<string, SecurityElliottWaves> | null,
		portfolios: [] as Portfolio[],
		accounts: [] as Account[],
		portfolio_id: null as string | null,
		account_id: null as string | null,
		...overrides
	};
}

/**
 * Render the page with the async holdings load stubbed, then wait until the
 * resolved rows are on screen. The page fetches its rows after navigation.
 */
async function renderWithHoldings(
	holdings: UserHolding[],
	dataOverrides: Parameters<typeof makeData>[0] = {},
	total = holdings.length
) {
	getUserHoldings.mockResolvedValue(pageOf(holdings, total));
	render(Page, { props: { data: makeData(dataOverrides) } });

	if (holdings.length > 0) {
		await waitFor(() => expect(screen.getAllByTestId('holding-row').length).toBeGreaterThan(0));
	} else {
		await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
	}
}

const testAccount1: Account = {
	id: 'acc-1',
	name: 'TFSA',
	external_id: 'ext-1',
	account_type_id: AccountType.TFSA,
	institution_id: Institution.Questrade,
	currency: 'CAD',
	is_active: true,
	api_sync_enabled: false,
	created_at: new Date('2025-01-01')
};

const testAccount2: Account = {
	id: 'acc-2',
	name: 'RRSP',
	external_id: 'ext-2',
	account_type_id: AccountType.RRSP,
	institution_id: Institution.Questrade,
	currency: 'CAD',
	is_active: true,
	api_sync_enabled: false,
	created_at: new Date('2025-01-01')
};

const testAccount3: Account = {
	id: 'acc-3',
	name: 'USD Account',
	external_id: 'ext-3',
	account_type_id: AccountType.NonRegistered,
	institution_id: Institution.Questrade,
	currency: 'USD',
	is_active: true,
	api_sync_enabled: false,
	created_at: new Date('2025-01-01')
};

const testPortfolio: Portfolio = {
	id: 'port-1',
	name: 'Retirement',
	accounts: [testAccount2]
};

describe('Holdings page (+page.svelte)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		getUserHoldings.mockReset();
		getPreferences.mockReset();
		patchPreferences.mockReset();
		getAccountTotals.mockReset();

		getUserHoldings.mockResolvedValue(pageOf([]));
		getPreferences.mockResolvedValue({});
		patchPreferences.mockResolvedValue({});
		getAccountTotals.mockResolvedValue(makeTotals(0, 0));
		getValuationsBatch.mockReset();
		getValuationsBatch.mockResolvedValue([]);
		vi.mocked(getAccountService).mockReturnValue({
			getUserHoldings
		} as unknown as AccountService);
		vi.mocked(getAccountClient).mockReturnValue({
			getAccountTotals
		} as unknown as AccountClient);
		vi.mocked(getMarketService).mockReturnValue({
			getValuationsBatch
		} as unknown as MarketService);
		vi.mocked(getUserPreferencesService).mockReturnValue({
			getPreferences,
			patchPreferences
		} as unknown as UserPreferencesService);
	});

	it('renders the shell (title, actions, table headers, skeletons) before holdings resolve', async () => {
		let resolveLoad!: (value: unknown) => void;
		getUserHoldings.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveLoad = resolve;
			})
		);

		render(Page, {
			props: {
				data: makeData({
					holdings_table_config: normalizeHoldingsTableConfig({
						widths: { security_symbol: 300 },
						visible: ['security_symbol', 'quantity', 'total_value']
					})
				})
			}
		});

		await waitFor(() => expect(screen.getAllByTestId('skeleton-row').length).toBeGreaterThan(0));

		expect(screen.getByText('Holdings')).toBeInTheDocument();
		expect(screen.getByText('All holdings across your accounts')).toBeInTheDocument();
		expect(screen.getByTestId('display-settings-trigger')).toBeInTheDocument();
		// The persisted column config is applied on the first render.
		expect(screen.getAllByRole('columnheader')).toHaveLength(3);
		expect(screen.queryByTestId('holding-row')).not.toBeInTheDocument();

		resolveLoad(pageOf([aaplTfsa], 1));

		await waitFor(() => expect(screen.getAllByTestId('holding-row')).toHaveLength(1));
	});

	it('fills in rows without user action once the async load resolves', async () => {
		await renderWithHoldings([aaplTfsa, msftRrsp, aaplUsd]);

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		expect(screen.getByText('TFSA')).toBeInTheDocument();
		expect(screen.getByText('USD Account')).toBeInTheDocument();
		expect(getUserHoldings).toHaveBeenCalledWith(0, 50, undefined);
	});

	it('loads every page of holdings sequentially', async () => {
		const firstPage = Array.from({ length: 50 }, (_, index) =>
			makeRow({
				id: `h-${index}`,
				security_id: `sec-${index}`,
				security_symbol: `SYM${index}`,
				security_name: `Security ${index}`
			})
		);
		const secondPage = [
			makeRow({
				id: 'h-50',
				security_id: 'sec-50',
				security_symbol: 'SYM50',
				security_name: 'Security 50'
			})
		];

		getUserHoldings
			.mockResolvedValueOnce(pageOf(firstPage, 51))
			.mockResolvedValueOnce(pageOf(secondPage, 51));

		render(Page, { props: { data: makeData() } });

		await waitFor(() => expect(screen.getAllByTestId('holding-row')).toHaveLength(51));
		expect(getUserHoldings).toHaveBeenNthCalledWith(1, 0, 50, undefined);
		expect(getUserHoldings).toHaveBeenNthCalledWith(2, 50, 50, undefined);
	});

	it('aggregates header totals per currency from the account totals', async () => {
		getAccountTotals.mockImplementation(async (id: string) => {
			if (id === 'acc-1')
				return makeTotals(1000, 100, {
					basis: 'net_deposits',
					net_deposits: { value: '900' }
				});
			if (id === 'acc-2')
				return makeTotals(500, 50, {
					basis: 'net_deposits',
					net_deposits: { value: '450' }
				});
			return makeTotals(200, 20, { basis: 'cost' });
		});

		await renderWithHoldings([aaplTfsa, aaplRrsp, aaplUsd], {
			accounts: [testAccount1, testAccount2, testAccount3]
		});

		// One CAD bucket and one USD bucket, never summed together.
		expect(screen.getAllByTestId(/^currency-.*-total-value$/)).toHaveLength(2);

		const cadTotalBtn = await screen.findByTestId('currency-CAD-total-value');
		expect(cadTotalBtn).toHaveTextContent('$1,500.00');

		// 150 / 1350 * 100
		const cadReturnPill = screen.getByTestId('currency-CAD-return-percent');
		expect(cadReturnPill).toHaveTextContent('+11.11%');
		expect(cadReturnPill.className).toContain('text-emerald-600');

		expect(screen.getByTestId('currency-CAD-profit-loss-value')).toHaveTextContent('+$150.00');

		expect(screen.getByTestId('currency-USD-total-value')).toHaveTextContent('US$200.00');
		expect(screen.getByTestId('currency-USD-profit-loss-value')).toHaveTextContent('+US$20.00');
	});

	it('uses the filtered account totals verbatim, including cash', async () => {
		getAccountTotals.mockImplementation(async (id: string) => {
			if (id === 'acc-1')
				return makeTotals(1234.56, 234.56, {
					basis: 'net_deposits',
					net_deposits: { value: '1000' }
				});
			return makeTotals(0, 0);
		});

		await renderWithHoldings([aaplTfsa], {
			accounts: [testAccount1, testAccount2],
			account_id: 'acc-1'
		});

		const totalValueBtn = await screen.findByTestId('currency-CAD-total-value');
		expect(totalValueBtn).toHaveTextContent('$1,234.56');
		expect(screen.getByTestId('currency-CAD-profit-loss-value')).toHaveTextContent('+$234.56');
		// Only the selected account's bucket is shown.
		expect(screen.getAllByTestId(/^currency-.*-total-value$/)).toHaveLength(1);
	});

	it('labels a mixed-basis currency bucket "mixed basis" in the tooltip', async () => {
		const user = userEvent.setup();
		getAccountTotals.mockImplementation(async (id: string) =>
			id === 'acc-1'
				? makeTotals(1000, 100, { basis: 'net_deposits', net_deposits: { value: '900' } })
				: makeTotals(500, 50, { basis: 'cost' })
		);

		await renderWithHoldings([aaplTfsa, aaplRrsp], {
			accounts: [testAccount1, testAccount2]
		});

		await screen.findByTestId('currency-CAD-total-value');
		await user.hover(screen.getByTestId('currency-CAD-profit-loss'));

		expect(await screen.findByText('mixed basis')).toBeInTheDocument();
	});

	it('shows the aggregated net deposits amount in the profit/loss tooltip for a net-deposits bucket', async () => {
		const user = userEvent.setup();
		getAccountTotals.mockResolvedValue(
			makeTotals(1000, 100, { basis: 'net_deposits', net_deposits: { value: '850' } })
		);

		await renderWithHoldings([aaplTfsa], { accounts: [testAccount1] });

		await screen.findByTestId('currency-CAD-total-value');
		await user.hover(screen.getByTestId('currency-CAD-profit-loss'));

		expect(await screen.findByText('net deposits basis: $850.00')).toBeInTheDocument();
		// The derived cost (1000 - 100 = $900.00) must not stand in for the basis.
		expect(screen.queryByText(/Total cost/)).not.toBeInTheDocument();
	});

	it('renders currency totals using TotalProfitLossButtons with split value and profit/loss buttons', async () => {
		getAccountTotals.mockResolvedValue(
			makeTotals(1000, 100, { basis: 'net_deposits', net_deposits: { value: '1000' } })
		);

		await renderWithHoldings([aaplTfsa], { accounts: [testAccount1] });

		const totalValueBtn = await screen.findByTestId('currency-CAD-total-value');
		const profitLossBtn = screen.getByTestId('currency-CAD-profit-loss');
		expect(totalValueBtn).toBeInTheDocument();
		expect(profitLossBtn).toBeInTheDocument();
		expect(totalValueBtn).toHaveTextContent('$1,000.00');
		expect(screen.getByTestId('currency-CAD-return-percent')).toHaveTextContent('+10.00%');
		expect(screen.getByTestId('currency-CAD-profit-loss-value')).toHaveTextContent('+$100.00');
	});

	it('renders negative return % pill badge with negative styling', async () => {
		getAccountTotals.mockResolvedValue(
			makeTotals(800, -200, { basis: 'net_deposits', net_deposits: { value: '1000' } })
		);

		await renderWithHoldings([aaplTfsa], { accounts: [testAccount1] });

		const pill = await screen.findByTestId('currency-CAD-return-percent');
		expect(pill).toHaveTextContent('-20.00%');
		expect(pill.className).toContain('text-rose-600');
		expect(screen.getByTestId('currency-CAD-profit-loss-value')).toHaveTextContent('-$200.00');
	});

	it('omits the return % pill when the bucket denominator is zero but keeps the dollar profit/loss', async () => {
		getAccountTotals.mockResolvedValue(makeTotals(500, 500, { basis: 'cost' }));

		await renderWithHoldings([aaplTfsa], { accounts: [testAccount1] });

		// value - profit_loss is zero here, so there is no meaningful percentage.
		expect(await screen.findByTestId('currency-CAD-total-value')).toHaveTextContent('$500.00');
		expect(screen.queryByTestId('currency-CAD-return-percent')).not.toBeInTheDocument();
		expect(screen.getByTestId('currency-CAD-profit-loss-value')).toHaveTextContent('+$500.00');
	});

	it('requests account totals after navigation without blocking the shell', async () => {
		let resolveLoad!: (value: unknown) => void;
		getUserHoldings.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveLoad = resolve;
			})
		);

		render(Page, { props: { data: makeData({ accounts: [testAccount1] }) } });

		// The shell is already painted while the holdings wave is still in flight.
		expect(screen.getByText('Holdings')).toBeInTheDocument();
		await waitFor(() => expect(getAccountTotals).toHaveBeenCalledWith('acc-1', undefined));

		resolveLoad(pageOf([]));
		await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
	});

	it('omits the account whose totals request fails and shows the existing error banner', async () => {
		getAccountTotals.mockImplementation(async (id: string) => {
			if (id === 'acc-1') {
				return makeTotals(1000, 100, {
					basis: 'net_deposits',
					net_deposits: { value: '900' }
				});
			}
			throw new Error('Totals service unavailable');
		});

		await renderWithHoldings([aaplTfsa, aaplRrsp], {
			accounts: [testAccount1, testAccount2]
		});

		await waitFor(() =>
			expect(screen.getByTestId('holdings-error')).toHaveTextContent('Totals service unavailable')
		);
		// acc-2 failed, so only acc-1's value is summed into the CAD bucket.
		expect(await screen.findByTestId('currency-CAD-total-value')).toHaveTextContent('$1,000.00');
	});

	it('renders unified icon-only settings trigger button and no standalone group checkbox in header', async () => {
		await renderWithHoldings([aaplTfsa]);

		const trigger = screen.getByRole('button', { name: 'Settings' });
		expect(trigger).toBeInTheDocument();
		expect(trigger).toHaveAttribute('data-testid', 'display-settings-trigger');
		expect(trigger).toHaveAttribute('aria-label', 'Settings');
		expect(trigger).toHaveAttribute('title', 'Settings');

		// Standalone checkbox outside dropdown is not present
		expect(screen.queryByRole('checkbox', { name: 'Group by stock' })).not.toBeInTheDocument();
		expect(screen.queryByTestId('column-visibility-trigger')).not.toBeInTheDocument();
		expect(screen.queryByTestId('holdings-filter-trigger')).not.toBeInTheDocument();
	});

	it('toggling "Group by stock" merges rows into single rows per stock without refetching', async () => {
		await renderWithHoldings([aaplTfsa, msftRrsp, aaplRrsp]);

		expect(screen.queryByTestId('group-header')).not.toBeInTheDocument();
		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		const callsAfterLoad = getUserHoldings.mock.calls.length;

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		// 3 holdings collapse into 2 stock rows (AAPL and MSFT) without accordion headers
		expect(screen.queryByTestId('group-header')).not.toBeInTheDocument();
		expect(screen.getAllByTestId('holding-row')).toHaveLength(2);

		// Grouping is pure client-side derivation: the table must not reload data.
		expect(getUserHoldings.mock.calls.length).toBe(callsAfterLoad);
	});

	it('un-groups again when the toggle is switched off', async () => {
		await renderWithHoldings([aaplTfsa, msftRrsp, aaplRrsp], { group_mode: 'stock' });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(2);

		const callsAfterLoad = getUserHoldings.mock.calls.length;

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		expect(getUserHoldings.mock.calls.length).toBe(callsAfterLoad);
	});

	it('restores the persisted group mode from the server data', async () => {
		await renderWithHoldings([aaplTfsa, aaplRrsp], { group_mode: 'stock' });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(1);
		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const item = await screen.findByTestId('group-by-stock');
		expect(item).toHaveAttribute('data-state', 'checked');
	});

	it('persists the group mode as "stock" when toggled', async () => {
		await renderWithHoldings([aaplTfsa]);

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		await waitFor(() => expect(patchPreferences).toHaveBeenCalledWith({ holdings_group: 'stock' }));
	});

	it('renders the empty state when there are no holdings', async () => {
		await renderWithHoldings([]);

		expect(screen.getByTestId('empty-state')).toHaveTextContent(
			'No holdings yet. Import an account to see your holdings here.'
		);
		expect(screen.queryByTestId('currency-CAD-total-value')).not.toBeInTheDocument();
	});

	it('shows the holdings-error alert with the real message when the async load fails', async () => {
		getUserHoldings.mockRejectedValue(new Error('Holdings service unavailable'));

		render(Page, { props: { data: makeData() } });

		await waitFor(() =>
			expect(screen.getByTestId('holdings-error')).toHaveTextContent('Holdings service unavailable')
		);
		// The page shell survives the failed async load (no SvelteKit error page).
		expect(screen.getByText('Holdings')).toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();
	});

	it('redirects to login when the async holdings load returns 401', async () => {
		getUserHoldings.mockRejectedValue(new ApiError(401, 'Unauthorized'));

		render(Page, { props: { data: makeData() } });

		await waitFor(() => expect(goto).toHaveBeenCalledWith('/auth/login?clear_session=true'));
		expect(goto).toHaveBeenCalledTimes(1);
	});

	it('shows an error banner when persisting the group mode fails', async () => {
		patchPreferences.mockRejectedValueOnce(new Error('Preferences unavailable'));

		await renderWithHoldings([aaplTfsa, aaplRrsp]);

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		await waitFor(() =>
			expect(screen.getByTestId('holdings-error')).toHaveTextContent('Preferences unavailable')
		);
		// The toggle still applies optimistically while the write is retried later.
		expect(screen.getAllByTestId('holding-row')).toHaveLength(1);
	});

	it('renders the column config loaded from the server', async () => {
		await renderWithHoldings([aaplTfsa], {
			holdings_table_config: normalizeHoldingsTableConfig({
				widths: { security_symbol: 300 },
				visible: ['security_symbol', 'quantity', 'total_value']
			})
		});

		expect(screen.getAllByRole('columnheader')).toHaveLength(3);
		expect(screen.getByTestId('column-col-security_symbol').style.width).toBe('300px');
		expect(screen.queryByTestId('account-cell')).not.toBeInTheDocument();
	});

	it('persists the column config when a column is hidden', async () => {
		await renderWithHoldings([aaplTfsa]);

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		await fireEvent.click(await screen.findByTestId('column-toggle-account_name'));

		await waitFor(() => expect(patchPreferences).toHaveBeenCalled());

		const lastPayload = patchPreferences.mock.calls.at(-1)?.[0] as {
			holdings_table: { visible: string[] };
		};
		expect(lastPayload.holdings_table.visible).not.toContain('account_name');
	});

	it('toggles column visibility from PageHeader dropdown and restores column on repeat toggle', async () => {
		await renderWithHoldings([aaplTfsa]);

		expect(screen.getByTestId('column-col-account_name')).toBeInTheDocument();

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const toggle = await screen.findByTestId('column-toggle-account_name');

		await fireEvent.click(toggle);
		expect(screen.queryByTestId('column-col-account_name')).not.toBeInTheDocument();

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const restoreToggle = await screen.findByTestId('column-toggle-account_name');
		await fireEvent.click(restoreToggle);
		expect(screen.getByTestId('column-col-account_name')).toBeInTheDocument();
	});

	it('forwards elliott_waves from data to HoldingsTable rendering projections', async () => {
		const mockWaves: Record<string, SecurityElliottWaves> = {
			'sec-aapl': {
				waves: [
					{
						id: 'w-1',
						degree: 'primary',
						type: 'impulse',
						wave5Target: 200,
						points: [{ wave: 5, price: 200, time: '2026-01-01' }]
					}
				]
			}
		};

		await renderWithHoldings([aaplTfsa], { elliott_waves: mockWaves });

		// AAPL latest_price is 100, wave 5 target is 200 -> upside +100%
		expect(screen.getByTestId('ew-primary-upside')).toHaveTextContent('+100.00%');
		expect(screen.getByTestId('ew-primary-target')).toHaveTextContent('$200.00');
	});

	describe('portfolio and account filtering', () => {
		it('filters displayed holdings to portfolio accounts when portfolio_id is provided in data', async () => {
			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				portfolios: [testPortfolio],
				accounts: [testAccount1, testAccount2],
				portfolio_id: 'port-1'
			});

			// Only acc-2 holdings (aaplRrsp and msftRrsp) should be rendered
			const rows = screen.getAllByTestId('holding-row');
			expect(rows).toHaveLength(2);
			expect(screen.queryByText('TFSA')).not.toBeInTheDocument();
			expect(screen.getAllByText('RRSP')).toHaveLength(2);
		});

		it('renders filter options in settings dropdown and allows selecting specific portfolio, account, and all', async () => {
			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				portfolios: [testPortfolio],
				accounts: [testAccount1, testAccount2]
			});

			expect(screen.queryByTestId('holdings-filter-trigger')).not.toBeInTheDocument();

			const settingsTrigger = screen.getByTestId('display-settings-trigger');
			expect(settingsTrigger).toBeInTheDocument();

			// Open dropdown
			await fireEvent.click(settingsTrigger);

			const portfolioOption = await screen.findByTestId('filter-portfolio-port-1');
			const accountOption = await screen.findByTestId('filter-account-acc-1');
			const allOption = await screen.findByTestId('filter-all');

			expect(portfolioOption).toBeInTheDocument();
			expect(accountOption).toBeInTheDocument();
			expect(allOption).toBeInTheDocument();
			expect(allOption).toHaveTextContent('All accounts');

			const portfoliosLabel = screen.getByText('Portfolios');
			const accountsLabel = screen.getByText('Accounts');
			expect(portfoliosLabel.compareDocumentPosition(portfolioOption)).toBe(
				Node.DOCUMENT_POSITION_FOLLOWING
			);
			expect(portfolioOption.compareDocumentPosition(accountsLabel)).toBe(
				Node.DOCUMENT_POSITION_FOLLOWING
			);
			expect(accountsLabel.compareDocumentPosition(allOption)).toBe(
				Node.DOCUMENT_POSITION_FOLLOWING
			);
			expect(allOption.compareDocumentPosition(accountOption)).toBe(
				Node.DOCUMENT_POSITION_FOLLOWING
			);

			// Select portfolio
			await fireEvent.click(portfolioOption);
			expect(goto).toHaveBeenCalledWith('/holdings?portfolio_id=port-1', expect.anything());

			// Filtered to acc-2 (2 rows)
			expect(screen.getAllByTestId('holding-row')).toHaveLength(2);

			// Select account
			await fireEvent.click(settingsTrigger);
			await fireEvent.click(await screen.findByTestId('filter-account-acc-1'));
			expect(goto).toHaveBeenCalledWith('/holdings?account_id=acc-1', expect.anything());
			expect(screen.getAllByTestId('holding-row')).toHaveLength(1);

			// Reset to All
			await fireEvent.click(settingsTrigger);
			await fireEvent.click(await screen.findByTestId('filter-all'));
			expect(goto).toHaveBeenCalledWith('/holdings', expect.anything());
			expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		});

		it('filters the list by account when an account badge is clicked', async () => {
			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				accounts: [testAccount1, testAccount2]
			});

			expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

			await fireEvent.click(screen.getByRole('button', { name: 'Filter by TFSA' }));

			expect(goto).toHaveBeenCalledWith('/holdings?account_id=acc-1', expect.anything());
			expect(screen.getAllByTestId('holding-row')).toHaveLength(1);
			expect(screen.getByTestId('breadcrumb-holdings')).toBeInTheDocument();
			expect(screen.getByTestId('breadcrumb-account-trigger')).toHaveTextContent('TFSA');
			expect(screen.queryByTestId('holdings-filter-trigger')).not.toBeInTheDocument();
		});

		it('renders breadcrumbs when filtered by portfolio and allows switching or clearing', async () => {
			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				portfolios: [testPortfolio],
				accounts: [testAccount1, testAccount2],
				portfolio_id: 'port-1'
			});

			expect(screen.getByTestId('breadcrumb-holdings')).toBeInTheDocument();
			const portTrigger = screen.getByTestId('breadcrumb-portfolio-trigger');
			expect(portTrigger).toHaveTextContent('Retirement');

			// Clicking breadcrumb-holdings clears filter to /holdings
			await fireEvent.click(screen.getByTestId('breadcrumb-holdings'));
			expect(goto).toHaveBeenCalledWith('/holdings', expect.anything());
			expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		});

		it('renders breadcrumbs when filtered by account with assigned portfolio and allows switching', async () => {
			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				portfolios: [testPortfolio],
				accounts: [testAccount1, testAccount2],
				account_id: 'acc-2'
			});

			// acc-2 is in testPortfolio ('Retirement')
			expect(screen.getByTestId('breadcrumb-holdings')).toBeInTheDocument();
			expect(screen.getByTestId('breadcrumb-portfolio-trigger')).toHaveTextContent('Retirement');
			const accTrigger = screen.getByTestId('breadcrumb-account-trigger');
			expect(accTrigger).toHaveTextContent('RRSP');

			// Clicking account trigger opens dropdown and allows switching account
			await fireEvent.click(accTrigger);
			const tfsaOption = await screen.findByTestId('breadcrumb-account-acc-1');
			expect(tfsaOption).toBeInTheDocument();

			await fireEvent.click(tfsaOption);
			expect(goto).toHaveBeenCalledWith('/holdings?account_id=acc-1', expect.anything());
		});

		it('updates valuation in table when saved in ValuationModal without page reload', async () => {
			vi.mocked(valuationClient.setValuation).mockResolvedValue({
				id: 1,
				user_id: 'u-1',
				security_id: 'sec-aapl',
				lower_bound: 150,
				upper_bound: 250,
				created_at: '2026-10-01T00:00:00Z',
				updated_at: '2026-10-07T00:00:00Z'
			});

			await renderWithHoldings([aaplTfsa]);

			const trigger = screen.getByTestId('valuation-edit-trigger');
			expect(trigger).toHaveTextContent('—');

			await fireEvent.click(trigger);
			expect(screen.getByText('Set Valuation Range')).toBeInTheDocument();

			await fireEvent.input(screen.getByLabelText('Lower Bound'), { target: { value: '150' } });
			await fireEvent.input(screen.getByLabelText('Upper Bound'), { target: { value: '250' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save Valuation' }));

			await waitFor(() => {
				expect(trigger).toHaveTextContent('150.00 – 250.00');
			});
		});

		it('updates currency totals when holdings are filtered by portfolio', async () => {
			getAccountTotals.mockImplementation(async (id: string) =>
				id === 'acc-1' ? makeTotals(1000, 100) : makeTotals(900, 30)
			);

			await renderWithHoldings([aaplTfsa, aaplRrsp, msftRrsp], {
				portfolios: [testPortfolio],
				accounts: [testAccount1, testAccount2]
			});

			// Initial CAD total across both accounts: 1000 + 900 = 1900
			expect(await screen.findByTestId('currency-CAD-total-value')).toHaveTextContent('$1,900.00');

			// Filter to portfolio port-1 (only acc-2)
			await fireEvent.click(screen.getByTestId('display-settings-trigger'));
			await fireEvent.click(await screen.findByTestId('filter-portfolio-port-1'));

			expect(screen.getByTestId('currency-CAD-total-value')).toHaveTextContent('$900.00');
		});
	});

	it('toggles Valuation Range column from settings dropdown and persists preference', async () => {
		await renderWithHoldings([aaplTfsa]);

		expect(screen.getByTestId('column-col-valuation_range')).toBeInTheDocument();

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const toggle = await screen.findByTestId('column-toggle-valuation_range');
		expect(toggle).toBeInTheDocument();

		await fireEvent.click(toggle);
		expect(screen.queryByTestId('column-col-valuation_range')).not.toBeInTheDocument();

		await waitFor(() => expect(patchPreferences).toHaveBeenCalled());
		const lastPayload = patchPreferences.mock.calls.at(-1)?.[0] as {
			holdings_table: { visible: string[] };
		};
		expect(lastPayload.holdings_table.visible).not.toContain('valuation_range');
	});
});
