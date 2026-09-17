import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';
import HoldingsTable from './holdings-table.svelte';
import type { UserHolding } from '$lib/types/account';

// The component is presentational — no API calls to mock. `$app/paths` is mocked
// so `resolve` returns a plain path (per frontend/AGENTS.md testing rules).
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

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
		account_id: 'acc-test-1',
		account_name: 'Test Account',
		...overrides
	};
}

const sortRows: UserHolding[] = [
	makeRow({
		id: 'h-z',
		security_id: 'sec-z',
		security_symbol: 'ZZZ',
		security_name: 'Zeta Corp',
		quantity: 5,
		average_cost: 10,
		converted_average_cost: 10,
		latest_price: 10,
		converted_latest_price: 10,
		total_value: 50,
		unconverted_total_value: 50,
		profit_loss: 5,
		unconverted_profit_loss: 5
	}),
	makeRow({
		id: 'h-a',
		security_id: 'sec-a',
		security_symbol: 'AAA',
		security_name: 'Alpha Corp',
		quantity: 10,
		average_cost: null,
		converted_average_cost: null,
		latest_price: undefined,
		converted_latest_price: null,
		total_value: 500,
		unconverted_total_value: 500,
		profit_loss: null,
		unconverted_profit_loss: null
	}),
	makeRow({
		id: 'h-m',
		security_id: 'sec-m',
		security_symbol: 'MMM',
		security_name: 'Mid Corp',
		quantity: 2,
		average_cost: 30,
		converted_average_cost: 30,
		latest_price: 30,
		converted_latest_price: 30,
		total_value: 60,
		unconverted_total_value: 60,
		profit_loss: -5,
		unconverted_profit_loss: -5
	})
];

const groupRows: UserHolding[] = [
	makeRow({
		id: 'g-1',
		security_id: 'sec-aapl',
		security_symbol: 'AAPL',
		security_name: 'Apple Inc.',
		quantity: 10,
		average_cost: 150,
		converted_average_cost: 205,
		latest_price: 180,
		converted_latest_price: 250,
		total_value: 1800,
		unconverted_total_value: 1300,
		profit_loss: 300,
		unconverted_profit_loss: 220,
		currency: 'CAD',
		security_currency: 'USD',
		account_id: 'acc-1',
		account_name: 'TFSA'
	}),
	makeRow({
		id: 'g-2',
		security_id: 'sec-msft',
		security_symbol: 'MSFT',
		security_name: 'Microsoft Corp.',
		quantity: 5,
		average_cost: 400,
		converted_average_cost: 400,
		latest_price: 200,
		converted_latest_price: 200,
		total_value: 1000,
		unconverted_total_value: 1000,
		profit_loss: -100,
		unconverted_profit_loss: -100,
		account_id: 'acc-2',
		account_name: 'RRSP'
	}),
	makeRow({
		id: 'g-3',
		security_id: 'sec-aapl',
		security_symbol: 'AAPL',
		security_name: 'Apple Inc.',
		quantity: 2,
		average_cost: null,
		converted_average_cost: null,
		latest_price: undefined,
		converted_latest_price: null,
		total_value: 500,
		unconverted_total_value: 500,
		profit_loss: null,
		unconverted_profit_loss: null,
		account_id: 'acc-1',
		account_name: 'TFSA'
	})
];

function renderedSymbols(): (string | null | undefined)[] {
	return screen
		.getAllByTestId('holding-row')
		.map((row) => within(row).getByTestId('security-symbol').textContent?.trim());
}

function rowBySymbol(symbol: string): HTMLElement {
	const row = screen
		.getAllByTestId('holding-row')
		.find((r) => within(r).getByTestId('security-symbol').textContent?.trim() === symbol);
	if (!row) throw new Error(`No rendered holding row for symbol ${symbol}`);
	return row;
}

describe('HoldingsTable', () => {
	it('sorts by the security string column, toggling asc/desc on repeat clicks', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);
	});

	it('sorts by a numeric column, toggling asc/desc on repeat clicks', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
		expect(renderedSymbols()).toEqual(['AAA', 'ZZZ', 'MMM']);

		await fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);
	});

	it('sorts null cells last in both directions', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		// Avg Cost: AAA has a null average_cost and must stay last in both directions.
		await fireEvent.click(screen.getByRole('button', { name: 'Avg Cost' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'Avg Cost' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);
	});

	it('sorts by the derived P/L % column', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('button', { name: /P\/L %/ }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: /P\/L %/ }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);
	});

	it('renders one row per holding and links each security cell to /security/{id}', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		const links = screen.getAllByTestId('security-link');
		expect(links[0]).toHaveAttribute('href', '/security/sec-a');
		expect(links[1]).toHaveAttribute('href', '/security/sec-m');
		expect(links[2]).toHaveAttribute('href', '/security/sec-z');
	});

	it('shows a dash in the account cell when the account name is blank', () => {
		render(HoldingsTable, {
			props: {
				holdings: [
					makeRow({
						id: 'h-blank-account',
						security_id: 'sec-blank',
						security_symbol: 'BLNK',
						security_name: 'Blank Corp',
						account_name: ''
					})
				]
			}
		});

		for (const cell of screen.getAllByTestId('account-cell')) {
			expect(cell).toHaveTextContent('-');
		}
	});

	it('colours positive and negative P/L cells and prefixes the P/L % sign', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		const positiveRow = rowBySymbol('ZZZ');
		expect(within(positiveRow).getByTestId('profit-loss')).toHaveClass('text-emerald-600');
		expect(within(positiveRow).getByTestId('profit-loss').textContent).toMatch(/^\+/);
		expect(within(positiveRow).getByTestId('profit-loss-percent')).toHaveClass('text-emerald-600');
		expect(within(positiveRow).getByTestId('profit-loss-percent')).toHaveTextContent('+10.00%');

		const negativeRow = rowBySymbol('MMM');
		expect(within(negativeRow).getByTestId('profit-loss')).toHaveClass('text-rose-600');
		expect(within(negativeRow).getByTestId('profit-loss').textContent).toMatch(/^-/);
		expect(within(negativeRow).getByTestId('profit-loss-percent')).toHaveClass('text-rose-600');
		expect(within(negativeRow).getByTestId('profit-loss-percent')).toHaveTextContent('-8.33%');
	});

	it('renders a group header per company with aggregated values', () => {
		render(HoldingsTable, { props: { holdings: groupRows, groupBy: 'company' } });

		const headers = screen.getAllByTestId('group-header');
		expect(headers).toHaveLength(2);

		const appleHeader = headers[0];
		expect(appleHeader).toHaveTextContent('Apple Inc.');
		expect(appleHeader).toHaveTextContent('2 holdings');
		expect(appleHeader).toHaveTextContent('2,300.00');
		expect(appleHeader).toHaveTextContent('+300.00');
		expect(appleHeader).toHaveTextContent('+14.63%');

		const microsoftHeader = headers[1];
		expect(microsoftHeader).toHaveTextContent('Microsoft Corp.');
		expect(microsoftHeader).toHaveTextContent('1 holding');
		expect(microsoftHeader).toHaveTextContent('1,000.00');
		expect(microsoftHeader).toHaveTextContent('-100.00');
		expect(microsoftHeader).toHaveTextContent('-5.00%');
	});

	it('collapses and expands a group rows on header click', async () => {
		render(HoldingsTable, { props: { holdings: groupRows, groupBy: 'company' } });

		expect(renderedSymbols()).toEqual(['AAPL', 'AAPL', 'MSFT']);

		const appleHeader = screen.getAllByTestId('group-header')[0];
		await fireEvent.click(appleHeader);

		expect(screen.getAllByTestId('group-header')).toHaveLength(2);
		expect(renderedSymbols()).toEqual(['MSFT']);
		expect(appleHeader).toHaveAttribute('aria-expanded', 'false');

		await fireEvent.click(appleHeader);
		expect(renderedSymbols()).toEqual(['AAPL', 'AAPL', 'MSFT']);
		expect(appleHeader).toHaveAttribute('aria-expanded', 'true');
	});

	it('renders the empty state when there are no rows', () => {
		render(HoldingsTable, { props: { holdings: [] } });

		expect(screen.getByTestId('empty-state')).toHaveTextContent('No holdings yet.');
		expect(screen.queryAllByTestId('holding-row')).toHaveLength(0);
	});

	it('renders a custom empty message', () => {
		render(HoldingsTable, { props: { holdings: [], emptyMessage: 'Nothing here.' } });

		expect(screen.getByTestId('empty-state')).toHaveTextContent('Nothing here.');
	});

	it('renders skeleton rows while loading instead of data or the empty state', () => {
		render(HoldingsTable, { props: { holdings: groupRows, isLoading: true } });

		expect(screen.getAllByTestId('skeleton-row')).toHaveLength(5);
		expect(screen.queryAllByTestId('holding-row')).toHaveLength(0);
		expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
	});
});
