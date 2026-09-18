import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';
import HoldingsTable from './holdings-table.svelte';
import type { UserHolding } from '$lib/types/account';
import { normalizeHoldingsTableConfig, type HoldingsTableConfig } from './holdings-table-columns';

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
		unconverted_profit_loss: 5,
		account_name: 'Account Z'
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
		unconverted_profit_loss: null,
		account_name: 'Account A'
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
		unconverted_profit_loss: -5,
		account_name: 'Account M'
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
		total_value: 2050,
		unconverted_total_value: 1800,
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
		currency: 'CAD',
		security_currency: 'CAD',
		account_id: 'acc-2',
		account_name: 'RRSP'
	}),
	makeRow({
		id: 'g-3',
		security_id: 'sec-aapl',
		security_symbol: 'AAPL',
		security_name: 'Apple Inc.',
		quantity: 2,
		average_cost: 160,
		converted_average_cost: 210,
		latest_price: 180,
		converted_latest_price: 250,
		total_value: 420,
		unconverted_total_value: 360,
		profit_loss: 50,
		unconverted_profit_loss: 35,
		currency: 'CAD',
		security_currency: 'USD',
		account_id: 'acc-2',
		account_name: 'RRSP'
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

	it('renders one row per holding and links each security cell to /security/{id} with rounded hover and without underline', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		const links = screen.getAllByTestId('security-link');
		expect(links[0]).toHaveAttribute('href', '/security/sec-a');
		expect(links[1]).toHaveAttribute('href', '/security/sec-m');
		expect(links[2]).toHaveAttribute('href', '/security/sec-z');

		// Check rounded hover styling and absence of group-hover:underline
		for (const link of links) {
			expect(link.className).toContain('hover:bg-muted/80');
			expect(link.className).toContain('rounded-md');
			const symbol = within(link).getByTestId('security-symbol');
			expect(symbol.className).not.toContain('group-hover:underline');
		}
	});

	it('renders account badges using Badge variant="secondary" and a dash when blank', () => {
		render(HoldingsTable, {
			props: {
				holdings: [
					makeRow({
						id: 'h-with-account',
						security_id: 'sec-1',
						security_symbol: 'ONE',
						security_name: 'One Corp',
						account_name: 'TFSA'
					}),
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

		const cells = screen.getAllByTestId('account-cell');
		expect(cells[0]).toHaveTextContent('TFSA');
		const badge = within(cells[0]).getByText('TFSA');
		expect(badge).toBeInTheDocument();

		expect(cells[1]).toHaveTextContent('-');
	});

	it('renders watchlist pill badges for P/L % with emerald, rose, and muted styling', () => {
		render(HoldingsTable, {
			props: {
				holdings: [
					...sortRows,
					makeRow({
						id: 'h-zero',
						security_id: 'sec-zero',
						security_symbol: 'ZERO',
						security_name: 'Zero Corp',
						quantity: 1,
						average_cost: 10,
						converted_average_cost: 10,
						profit_loss: 0,
						total_value: 10
					})
				]
			}
		});

		const positiveRow = rowBySymbol('ZZZ');
		const posPill = within(positiveRow).getByTestId('profit-loss-percent');
		expect(posPill).toHaveClass('text-emerald-600');
		expect(posPill).toHaveClass('inline-flex');
		expect(posPill).toHaveClass('rounded-md');
		expect(posPill).toHaveClass('border');
		expect(posPill).toHaveTextContent('+10.00%');

		const negativeRow = rowBySymbol('MMM');
		const negPill = within(negativeRow).getByTestId('profit-loss-percent');
		expect(negPill).toHaveClass('text-rose-600');
		expect(negPill).toHaveClass('inline-flex');
		expect(negPill).toHaveClass('rounded-md');
		expect(negPill).toHaveTextContent('-8.33%');

		const zeroRow = rowBySymbol('ZERO');
		const zeroPill = within(zeroRow).getByTestId('profit-loss-percent');
		expect(zeroPill).toHaveClass('text-muted-foreground');
		expect(zeroPill).toHaveTextContent('+0.00%');
	});

	it('renders dollar Profit / Loss with colored text styling without pill badge containers', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		const positiveRow = rowBySymbol('ZZZ');
		const posPl = within(positiveRow).getByTestId('profit-loss');
		expect(posPl).toHaveClass('text-emerald-600');
		expect(posPl).toHaveClass('text-sm');
		expect(posPl.className).not.toContain('border');
		expect(posPl.textContent).toMatch(/^\+/);

		const negativeRow = rowBySymbol('MMM');
		const negPl = within(negativeRow).getByTestId('profit-loss');
		expect(negPl).toHaveClass('text-rose-600');
		expect(negPl).toHaveClass('text-sm');
		expect(negPl.className).not.toContain('border');
		expect(negPl.textContent).toMatch(/^-/);
	});

	it('renders dual-currency display with CAD on top and native USD on bottom, and price in native currency only', () => {
		render(HoldingsTable, {
			props: {
				holdings: [
					makeRow({
						id: 'h-usd-sec',
						security_id: 'sec-aapl',
						security_symbol: 'AAPL',
						security_name: 'Apple Inc.',
						currency: 'CAD',
						security_currency: 'USD',
						quantity: 10,
						average_cost: 150,
						converted_average_cost: 205,
						latest_price: 180,
						converted_latest_price: 245,
						total_value: 2450,
						unconverted_total_value: 1800,
						profit_loss: 400,
						unconverted_profit_loss: 300
					})
				]
			}
		});

		const row = rowBySymbol('AAPL');

		// Total Value: CAD on top, USD on bottom
		const totalValueCell = within(row).getAllByRole('cell')[5];
		expect(totalValueCell).toHaveTextContent('$2,450.00');
		expect(totalValueCell).toHaveTextContent('$1,800.00');

		// Avg Cost: CAD on top, USD on bottom
		const avgCostCell = within(row).getAllByRole('cell')[3];
		expect(avgCostCell).toHaveTextContent('$205.00');
		expect(avgCostCell).toHaveTextContent('$150.00');

		// Profit / Loss: CAD on top, USD on bottom
		expect(within(row).getByTestId('profit-loss')).toHaveTextContent('+$400.00');
		expect(within(row).getByTestId('profit-loss-secondary')).toHaveTextContent('+US$300.00');

		// Latest Price: only native USD, no CAD converted line
		const priceCell = within(row).getAllByRole('cell')[4];
		expect(priceCell).toHaveTextContent('$180.00');
		expect(priceCell).not.toHaveTextContent('$245.00');
	});

	it('renders "Group by stock" mode: strictly one row per stock without accordion headers and with combined account badges', () => {
		render(HoldingsTable, { props: { holdings: groupRows, groupBy: 'stock' } });

		// Strictly 2 rows (AAPL and MSFT), no accordion group-header or group-row elements
		expect(screen.queryByTestId('group-header')).not.toBeInTheDocument();
		expect(screen.queryByTestId('group-row')).not.toBeInTheDocument();
		expect(screen.getAllByTestId('holding-row')).toHaveLength(2);
		expect(renderedSymbols()).toEqual(['AAPL', 'MSFT']);

		// AAPL row aggregates CAD totals across TFSA and RRSP
		const aaplRow = rowBySymbol('AAPL');
		expect(within(aaplRow).getByText('TFSA')).toBeInTheDocument();
		expect(within(aaplRow).getByText('RRSP')).toBeInTheDocument();
		// Quantity: 10 + 2 = 12
		expect(within(aaplRow).getByText('12')).toBeInTheDocument();
		// CAD Total Value: 2050 + 420 = 2470
		expect(within(aaplRow).getByText('$2,470.00')).toBeInTheDocument();
		// CAD Profit Loss: 300 + 50 = +$350.00
		expect(within(aaplRow).getByTestId('profit-loss')).toHaveTextContent('+$350.00');

		// MSFT row
		const msftRow = rowBySymbol('MSFT');
		expect(within(msftRow).getByText('RRSP')).toBeInTheDocument();
		expect(within(msftRow).getByText('5')).toBeInTheDocument();
	});

	it('sorts aggregated stock rows in "Group by stock" mode', async () => {
		render(HoldingsTable, { props: { holdings: groupRows, groupBy: 'stock' } });

		// Default sort is total_value desc: AAPL ($2,470) then MSFT ($1,000)
		expect(renderedSymbols()).toEqual(['AAPL', 'MSFT']);

		// Sort by quantity: AAPL (12), MSFT (5)
		await fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
		expect(renderedSymbols()).toEqual(['AAPL', 'MSFT']);

		await fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
		expect(renderedSymbols()).toEqual(['MSFT', 'AAPL']);

		// Sort by Security symbol: AAPL, MSFT
		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['MSFT', 'AAPL']);

		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['AAPL', 'MSFT']);
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

	describe('column resize', () => {
		it('resizes the dragged column and leaves adjacent widths untouched', async () => {
			render(HoldingsTable, { props: { holdings: sortRows } });

			const handle = screen.getByTestId('column-resize-quantity');
			await fireEvent.pointerDown(handle, { clientX: 100, pointerId: 1 });
			await fireEvent.pointerMove(handle, { clientX: 150, pointerId: 1 });

			expect(screen.getByTestId('column-col-quantity').style.width).toBe('160px');
			expect(screen.getByTestId('column-col-security_symbol').style.width).toBe('220px');
			expect(screen.getByTestId('column-col-account_name').style.width).toBe('140px');

			await fireEvent.pointerUp(handle, { clientX: 150, pointerId: 1 });
		});

		it('clamps the dragged width to the per-column min and max', async () => {
			render(HoldingsTable, { props: { holdings: sortRows } });

			const handle = screen.getByTestId('column-resize-quantity');

			await fireEvent.pointerDown(handle, { clientX: 100, pointerId: 1 });
			await fireEvent.pointerMove(handle, { clientX: 10_000, pointerId: 1 });
			expect(screen.getByTestId('column-col-quantity').style.width).toBe('180px');

			await fireEvent.pointerMove(handle, { clientX: -10_000, pointerId: 1 });
			expect(screen.getByTestId('column-col-quantity').style.width).toBe('90px');

			await fireEvent.pointerUp(handle, { clientX: -10_000, pointerId: 1 });
		});

		it('emits the clamped config once the drag ends', async () => {
			const onConfigChange = vi.fn();
			render(HoldingsTable, { props: { holdings: sortRows, onConfigChange } });

			const handle = screen.getByTestId('column-resize-quantity');
			await fireEvent.pointerDown(handle, { clientX: 100, pointerId: 1 });
			await fireEvent.pointerMove(handle, { clientX: 150, pointerId: 1 });

			expect(onConfigChange).not.toHaveBeenCalled();

			await fireEvent.pointerUp(handle, { clientX: 150, pointerId: 1 });

			expect(onConfigChange).toHaveBeenCalledTimes(1);
			expect(onConfigChange.mock.calls[0][0].widths.quantity).toBe(160);
			expect(onConfigChange.mock.calls[0][0].visible).toEqual([
				'security_symbol',
				'account_name',
				'quantity',
				'average_cost',
				'latest_price',
				'total_value',
				'profit_loss',
				'profit_loss_percent'
			]);
		});

		it('ignores pointer moves when no drag is active', async () => {
			const onConfigChange = vi.fn();
			render(HoldingsTable, { props: { holdings: sortRows, onConfigChange } });

			await fireEvent.pointerMove(screen.getByTestId('column-resize-quantity'), {
				clientX: 500,
				pointerId: 1
			});

			expect(screen.getByTestId('column-col-quantity').style.width).toBe('110px');
			expect(onConfigChange).not.toHaveBeenCalled();
		});
	});

	describe('column visibility', () => {
		async function hideColumn(testId: string) {
			await fireEvent.click(screen.getByTestId('column-visibility-trigger'));
			const toggle = await screen.findByTestId(testId);
			await fireEvent.click(toggle);
		}

		it('hides a column from the header, rows and colgroup', async () => {
			render(HoldingsTable, { props: { holdings: groupRows, groupBy: 'stock' } });

			await hideColumn('column-toggle-account_name');

			expect(screen.queryByRole('button', { name: 'Account' })).not.toBeInTheDocument();
			expect(screen.queryByTestId('account-cell')).not.toBeInTheDocument();
			expect(screen.queryByTestId('column-col-account_name')).not.toBeInTheDocument();
			expect(screen.getByTestId('column-col-security_symbol')).toBeInTheDocument();
		});

		it('shrinks the empty-state colspan to the number of visible columns', async () => {
			render(HoldingsTable, { props: { holdings: [] } });

			await hideColumn('column-toggle-account_name');

			expect(screen.getByTestId('empty-state').querySelector('td')).toHaveAttribute('colspan', '7');
		});

		it('emits the updated config when a column is hidden and when it is restored', async () => {
			const onConfigChange = vi.fn();
			render(HoldingsTable, { props: { holdings: sortRows, onConfigChange } });

			await hideColumn('column-toggle-account_name');
			expect(onConfigChange).toHaveBeenCalledTimes(1);
			expect(onConfigChange.mock.calls[0][0].visible).not.toContain('account_name');

			await hideColumn('column-toggle-account_name');
			expect(onConfigChange).toHaveBeenCalledTimes(2);
			expect(onConfigChange.mock.calls[1][0].visible).toContain('account_name');
		});

		it('disables hiding the sticky first column', async () => {
			const onConfigChange = vi.fn();
			render(HoldingsTable, { props: { holdings: sortRows, onConfigChange } });

			await fireEvent.click(screen.getByTestId('column-visibility-trigger'));
			const stickyToggle = await screen.findByTestId('column-toggle-security_symbol');

			expect(stickyToggle).toHaveAttribute('aria-disabled', 'true');
			await fireEvent.click(stickyToggle);

			expect(onConfigChange).not.toHaveBeenCalled();
			expect(screen.getByTestId('column-col-security_symbol')).toBeInTheDocument();
		});
	});

	describe('persisted config restore', () => {
		it('renders a supplied config (custom widths, hidden columns) as-is', () => {
			const tableConfig = normalizeHoldingsTableConfig({
				widths: { security_symbol: 300 },
				visible: ['security_symbol', 'quantity', 'total_value']
			});

			render(HoldingsTable, { props: { holdings: sortRows, tableConfig } });

			expect(screen.getAllByRole('columnheader')).toHaveLength(3);
			expect(screen.getByTestId('column-col-security_symbol').style.width).toBe('300px');
			expect(screen.queryByTestId('account-cell')).not.toBeInTheDocument();
			expect(screen.getByTestId('column-col-total_value')).toBeInTheDocument();
		});

		it('falls back to the defaults for an invalid stored config', () => {
			const tableConfig = {
				widths: { quantity: 10_000, unknown: 50 },
				visible: ['not_a_column']
			} as unknown as HoldingsTableConfig;

			render(HoldingsTable, { props: { holdings: sortRows, tableConfig } });

			expect(screen.getAllByRole('columnheader')).toHaveLength(8);
			expect(screen.getByTestId('column-col-quantity').style.width).toBe('180px');
		});
	});
});
