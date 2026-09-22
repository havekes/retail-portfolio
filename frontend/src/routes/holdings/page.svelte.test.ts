import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { UserHolding } from '$lib/types/account';
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

vi.mock('$lib/api/userPreferencesService', () => ({
	getUserPreferencesService: vi.fn()
}));

import { goto } from '$app/navigation';
import { ApiError } from '$lib/api/apiClient';
import { getAccountService, type AccountService } from '$lib/api/accountService';
import {
	getUserPreferencesService,
	type UserPreferencesService
} from '$lib/api/userPreferencesService';

const getUserHoldings = vi.fn();
const getPreferences = vi.fn();
const patchPreferences = vi.fn();

function makeRow(
	overrides: Partial<UserHolding> &
		Pick<UserHolding, 'id' | 'security_id' | 'security_symbol' | 'security_name'>
): UserHolding {
	return {
		quantity: 1,
		average_cost: 100,
		total_value: 100,
		profit_loss: 0,
		currency: 'CAD',
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
	}> = {}
) {
	return {
		user: { id: 'u1', email: 'test@example.com' },
		sidebar_open: true,
		collapsed_watchlist_ids: [] as string[],
		watchlist_order: null as string[] | null,
		holdings_table_config: HOLDINGS_TABLE_DEFAULT_CONFIG,
		group_mode: 'none' as HoldingsGroupMode,
		elliott_waves: null as Record<string, SecurityElliottWaves> | null,
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

describe('Holdings page (+page.svelte)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		getUserHoldings.mockReset();
		getPreferences.mockReset();
		patchPreferences.mockReset();

		getUserHoldings.mockResolvedValue(pageOf([]));
		getPreferences.mockResolvedValue({});
		patchPreferences.mockResolvedValue({});
		vi.mocked(getAccountService).mockReturnValue({
			getUserHoldings
		} as unknown as AccountService);
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

	it('buckets header totals per currency instead of summing across them', async () => {
		await renderWithHoldings([aaplTfsa, aaplRrsp, aaplUsd]);

		const cad = screen.getByTestId('currency-total-CAD');
		expect(cad).toHaveTextContent('CAD TOTAL');
		expect(cad).toHaveTextContent('$1,500.00');

		const cadReturnPill = screen.getByTestId('currency-return-percent-CAD');
		expect(cadReturnPill).toHaveTextContent('+3.33%');
		expect(cadReturnPill.className).toContain('text-emerald-600');

		const cadPl = screen.getByTestId('currency-profit-loss-CAD');
		expect(cadPl).toHaveTextContent('+$50.00');

		const usd = screen.getByTestId('currency-total-USD');
		expect(usd).toHaveTextContent('USD TOTAL');
		expect(usd).toHaveTextContent('$200.00');

		const usdReturnPill = screen.getByTestId('currency-return-percent-USD');
		expect(usdReturnPill).toHaveTextContent('+20.00%');
		expect(usdReturnPill.className).toContain('text-emerald-600');

		const usdPl = screen.getByTestId('currency-profit-loss-USD');
		expect(usdPl).toHaveTextContent('+US$20.00');
	});

	it('renders negative return % pill badge with negative styling', async () => {
		const losingHolding = makeRow({
			id: 'h-loss',
			security_id: 'sec-loss',
			security_symbol: 'LOSS',
			security_name: 'Loss Corp',
			quantity: 10,
			average_cost: 100,
			converted_average_cost: 100,
			total_value: 800,
			profit_loss: -200,
			currency: 'CAD'
		});

		await renderWithHoldings([losingHolding]);

		const pill = screen.getByTestId('currency-return-percent-CAD');
		expect(pill).toHaveTextContent('-20.00%');
		expect(pill.className).toContain('text-rose-600');
		expect(screen.getByTestId('currency-profit-loss-CAD')).toHaveTextContent('-$200.00');
	});

	it('handles currency bucket with zero cost basis or missing profit/loss gracefully', async () => {
		const zeroCostHolding = makeRow({
			id: 'h-gift',
			security_id: 'sec-gift',
			security_symbol: 'GIFT',
			security_name: 'Gifted Sec',
			quantity: 10,
			average_cost: 0,
			converted_average_cost: 0,
			total_value: 500,
			profit_loss: 500,
			currency: 'CAD'
		});
		const noPlHolding = makeRow({
			id: 'h-nopl',
			security_id: 'sec-nopl',
			security_symbol: 'NOPL',
			security_name: 'No PL Sec',
			quantity: 5,
			average_cost: 100,
			converted_average_cost: 100,
			total_value: 500,
			profit_loss: null,
			currency: 'USD'
		});

		await renderWithHoldings([zeroCostHolding, noPlHolding]);

		// Zero cost basis -> returnPercent is null, pill badge omitted, but dollar profit/loss is displayed
		expect(screen.queryByTestId('currency-return-percent-CAD')).not.toBeInTheDocument();
		expect(screen.getByTestId('currency-profit-loss-CAD')).toHaveTextContent('+$500.00');

		// Missing profit/loss -> hasProfitLoss is false, right side (pill and dollar P/L) is omitted
		expect(screen.queryByTestId('currency-return-percent-USD')).not.toBeInTheDocument();
		expect(screen.queryByTestId('currency-profit-loss-USD')).not.toBeInTheDocument();
		expect(screen.getByTestId('currency-total-USD')).toHaveTextContent('$500.00');
	});

	it('renders unified icon-only settings trigger button and no standalone group checkbox in header', async () => {
		await renderWithHoldings([aaplTfsa]);

		const trigger = screen.getByRole('button', { name: 'Display settings' });
		expect(trigger).toBeInTheDocument();
		expect(trigger).toHaveAttribute('data-testid', 'display-settings-trigger');
		expect(trigger).toHaveAttribute('aria-label', 'Display settings');
		expect(trigger).toHaveAttribute('title', 'Display settings');

		// Standalone checkbox outside dropdown is not present
		expect(screen.queryByRole('checkbox', { name: 'Group by stock' })).not.toBeInTheDocument();
		expect(screen.queryByTestId('column-visibility-trigger')).not.toBeInTheDocument();
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
		expect(screen.queryByTestId('currency-total-CAD')).not.toBeInTheDocument();
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
});
