import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { UserHolding } from '$lib/types/account';
import {
	HOLDINGS_TABLE_DEFAULT_CONFIG,
	normalizeHoldingsTableConfig
} from '$lib/components/holdings/holdings-table-columns';

// No test may hit the network (frontend/AGENTS.md): every API module the page
// touches is mocked, and framework modules that touch the browser are stubbed.
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
		group_mode: 'none' | 'company';
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
		group_mode: 'none' as const,
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
		expect(cad).toHaveTextContent('CAD total');
		expect(cad).toHaveTextContent('1,500.00');
		expect(within(cad).getByText(/1,500\.00/)).toBeInTheDocument();

		const cadPl = screen.getByTestId('currency-profit-loss-CAD');
		expect(cadPl).toHaveTextContent('50.00');
		expect(cadPl).toHaveTextContent('P/L');

		const usd = screen.getByTestId('currency-total-USD');
		expect(usd).toHaveTextContent('USD total');
		expect(usd).toHaveTextContent('200.00');
	});

	it('toggling group by company merges rows for the same security without refetching', async () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa, msftRrsp, aaplRrsp] }) } });

		expect(screen.queryAllByTestId('group-header')).toHaveLength(0);
		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		await fireEvent.click(screen.getByTestId('group-by-company'));

		const headers = screen.getAllByTestId('group-header');
		expect(headers).toHaveLength(2);
		expect(headers[0]).toHaveTextContent('Apple Inc.');
		expect(headers[0]).toHaveTextContent('2 holdings');
		expect(screen.getByTestId('group-by-company')).toHaveAttribute('data-state', 'checked');

		// Grouping is pure client-side derivation: the table must not reload data.
		expect(getUserHoldings).not.toHaveBeenCalled();
	});

	it('un-groups again when the toggle is switched off', async () => {
		render(Page, {
			props: { data: makeData({ holdings: [aaplTfsa, msftRrsp, aaplRrsp], group_mode: 'company' }) }
		});

		expect(screen.getAllByTestId('group-header')).toHaveLength(2);

		await fireEvent.click(screen.getByTestId('group-by-company'));

		expect(screen.queryAllByTestId('group-header')).toHaveLength(0);
		expect(getUserHoldings).not.toHaveBeenCalled();
	});

	it('restores the persisted group mode from the server data', () => {
		render(Page, {
			props: { data: makeData({ holdings: [aaplTfsa, aaplRrsp], group_mode: 'company' }) }
		});

		expect(screen.getAllByTestId('group-header')).toHaveLength(1);
		expect(screen.getByTestId('group-by-company')).toHaveAttribute('data-state', 'checked');
	});

	it('persists the group mode when toggled', async () => {
		render(Page, { props: { data: makeData({ holdings: [aaplTfsa] }) } });

		await fireEvent.click(screen.getByTestId('group-by-company'));

		await waitFor(() =>
			expect(patchPreferences).toHaveBeenCalledWith({ holdings_group: 'company' })
		);
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

		await fireEvent.click(screen.getByTestId('group-by-company'));

		await waitFor(() =>
			expect(screen.getByTestId('holdings-error')).toHaveTextContent('Preferences unavailable')
		);
		// The toggle still applies optimistically while the write is retried later.
		expect(screen.getAllByTestId('group-header')).toHaveLength(1);
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

		await fireEvent.click(screen.getByTestId('column-visibility-trigger'));
		await fireEvent.click(await screen.findByTestId('column-toggle-account_name'));

		await waitFor(() => expect(patchPreferences).toHaveBeenCalled());

		const lastPayload = patchPreferences.mock.calls.at(-1)?.[0] as {
			holdings_table: { visible: string[] };
		};
		expect(lastPayload.holdings_table.visible).not.toContain('account_name');
	});
});
