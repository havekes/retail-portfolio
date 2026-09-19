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

vi.mock('$lib/api/accountService', () => ({
	getAccountService: vi.fn()
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	getUserPreferencesService: vi.fn()
}));

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

function makeData(
	overrides: Partial<{
		holdings: UserHolding[];
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
		watchlist_sort: null as Record<string, string> | null,
		holdings: [] as UserHolding[],
		holdings_table_config: HOLDINGS_TABLE_DEFAULT_CONFIG,
		group_mode: 'none' as HoldingsGroupMode,
		elliott_waves: null as Record<string, SecurityElliottWaves> | null,
		...overrides
	};
}

describe('Holdings page (+page.svelte)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		getUserHoldings.mockReset();
		getPreferences.mockReset();
		patchPreferences.mockReset();

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

	it('lists holdings from every account', () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa, msftRrsp, aaplUsd] }) } });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		expect(screen.getByText('TFSA')).toBeInTheDocument();
		expect(screen.getByText('USD Account')).toBeInTheDocument();
	});

	it('buckets header totals per currency instead of summing across them', () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa, aaplRrsp, aaplUsd] }) } });

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

	it('renders negative return % pill badge with negative styling', () => {
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
		render(Page, { props: { data: makeData({ holdings: [losingHolding] }) } });
		const pill = screen.getByTestId('currency-return-percent-CAD');
		expect(pill).toHaveTextContent('-20.00%');
		expect(pill.className).toContain('text-rose-600');
		expect(screen.getByTestId('currency-profit-loss-CAD')).toHaveTextContent('-$200.00');
	});

	it('handles currency bucket with zero cost basis or missing profit/loss gracefully', () => {
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
		render(Page, { props: { data: makeData({ holdings: [zeroCostHolding, noPlHolding] }) } });

		// Zero cost basis -> returnPercent is null, pill badge omitted, but dollar profit/loss is displayed
		expect(screen.queryByTestId('currency-return-percent-CAD')).not.toBeInTheDocument();
		expect(screen.getByTestId('currency-profit-loss-CAD')).toHaveTextContent('+$500.00');

		// Missing profit/loss -> hasProfitLoss is false, right side (pill and dollar P/L) is omitted
		expect(screen.queryByTestId('currency-return-percent-USD')).not.toBeInTheDocument();
		expect(screen.queryByTestId('currency-profit-loss-USD')).not.toBeInTheDocument();
		expect(screen.getByTestId('currency-total-USD')).toHaveTextContent('$500.00');
	});

	it('renders unified icon-only settings trigger button and no standalone group checkbox in header', () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa] }) } });

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
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa, msftRrsp, aaplRrsp] }) } });

		expect(screen.queryByTestId('group-header')).not.toBeInTheDocument();
		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		// 3 holdings collapse into 2 stock rows (AAPL and MSFT) without accordion headers
		expect(screen.queryByTestId('group-header')).not.toBeInTheDocument();
		expect(screen.getAllByTestId('holding-row')).toHaveLength(2);

		// Grouping is pure client-side derivation: the table must not reload data.
		expect(getUserHoldings).not.toHaveBeenCalled();
	});

	it('un-groups again when the toggle is switched off', async () => {
		render(Page, {
			props: { data: makeData({ holdings: [aaplTfsa, msftRrsp, aaplRrsp], group_mode: 'stock' }) }
		});

		expect(screen.getAllByTestId('holding-row')).toHaveLength(2);

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);
		expect(getUserHoldings).not.toHaveBeenCalled();
	});

	it('restores the persisted group mode from the server data', async () => {
		render(Page, {
			props: { data: makeData({ holdings: [aaplTfsa, aaplRrsp], group_mode: 'stock' }) }
		});

		expect(screen.getAllByTestId('holding-row')).toHaveLength(1);
		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const item = await screen.findByTestId('group-by-stock');
		expect(item).toHaveAttribute('data-state', 'checked');
	});

	it('persists the group mode as "stock" when toggled', async () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa] }) } });

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		await waitFor(() => expect(patchPreferences).toHaveBeenCalledWith({ holdings_group: 'stock' }));
	});

	it('renders the empty state when there are no holdings', () => {
		render(Page, { props: { data: makeData() } });

		expect(screen.getByTestId('empty-state')).toHaveTextContent(
			'No holdings yet. Import an account to see your holdings here.'
		);
		expect(screen.queryByTestId('currency-total-CAD')).not.toBeInTheDocument();
	});

	it('shows an error banner when persisting the group mode fails', async () => {
		patchPreferences.mockRejectedValueOnce(new Error('Preferences unavailable'));

		render(Page, { props: { data: makeData({ holdings: [aaplTfsa, aaplRrsp] }) } });

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		const groupByToggle = await screen.findByTestId('group-by-stock');
		await fireEvent.click(groupByToggle);

		await waitFor(() =>
			expect(screen.getByTestId('holdings-error')).toHaveTextContent('Preferences unavailable')
		);
		// The toggle still applies optimistically while the write is retried later.
		expect(screen.getAllByTestId('holding-row')).toHaveLength(1);
	});

	it('renders the column config loaded from the server', () => {
		render(Page, {
			props: {
				data: makeData({
					holdings: [aaplTfsa],
					holdings_table_config: normalizeHoldingsTableConfig({
						widths: { security_symbol: 300 },
						visible: ['security_symbol', 'quantity', 'total_value']
					})
				})
			}
		});

		expect(screen.getAllByRole('columnheader')).toHaveLength(3);
		expect(screen.getByTestId('column-col-security_symbol').style.width).toBe('300px');
		expect(screen.queryByTestId('account-cell')).not.toBeInTheDocument();
	});

	it('persists the column config when a column is hidden', async () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa] }) } });

		await fireEvent.click(screen.getByTestId('display-settings-trigger'));
		await fireEvent.click(await screen.findByTestId('column-toggle-account_name'));

		await waitFor(() => expect(patchPreferences).toHaveBeenCalled());

		const lastPayload = patchPreferences.mock.calls.at(-1)?.[0] as {
			holdings_table: { visible: string[] };
		};
		expect(lastPayload.holdings_table.visible).not.toContain('account_name');
	});

	it('toggles column visibility from PageHeader dropdown and restores column on repeat toggle', async () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa] }) } });

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

	it('forwards elliott_waves from data to HoldingsTable rendering projections', () => {
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

		render(Page, {
			props: {
				data: makeData({
					holdings: [aaplTfsa],
					elliott_waves: mockWaves
				})
			}
		});

		// AAPL latest_price is 100, wave 5 target is 200 -> upside +100%
		expect(screen.getByTestId('ew-primary-upside')).toHaveTextContent('+100.00%');
		expect(screen.getByTestId('ew-primary-target')).toHaveTextContent('$200.00');
	});
});
