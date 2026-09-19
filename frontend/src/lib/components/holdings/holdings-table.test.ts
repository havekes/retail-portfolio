import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/svelte';
import HoldingsTable from './holdings-table.svelte';
import type { UserHolding } from '$lib/types/account';
import type { SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import {
	HOLDINGS_TABLE_COLUMN_IDS,
	normalizeHoldingsTableConfig,
	type HoldingsTableConfig
} from './holdings-table-columns';

// The component is presentational — no API calls to mock. `$app/paths` is mocked
// so `resolve` returns a plain path (per frontend/AGENTS.md testing rules).
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

const sampleElliottWaves: Record<string, SecurityElliottWaves> = {
	'sec-z': {
		waves: [
			{
				id: 'w-z-primary',
				degree: 'primary',
				type: 'impulse',
				wave5Target: 20,
				points: [{ wave: 5, price: 20, time: '2026-01-01' }]
			},
			{
				id: 'w-z-cycle',
				degree: 'cycle',
				type: 'impulse',
				wave5Target: 25,
				points: [{ wave: 5, price: 25, time: '2026-01-01' }]
			}
		]
	},
	'sec-m': {
		waves: [
			{
				id: 'w-m-primary',
				degree: 'primary',
				type: 'impulse',
				wave5Target: 15,
				points: [{ wave: 5, price: 15, time: '2026-01-01' }]
			},
			{
				id: 'w-m-cycle',
				degree: 'cycle',
				type: 'impulse',
				wave5Target: 45,
				points: [{ wave: 5, price: 45, time: '2026-01-01' }]
			}
		]
	}
};

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
	it('sorts by clicking the Table.Head columnheader cell, toggling asc/desc on repeat clicks', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('columnheader', { name: /Security/i }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('columnheader', { name: /Security/i }));
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);
	});

	it('sorts via inner button without double-toggling from bubbling', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'Security' }));
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);
	});

	it('sorts by a numeric column, toggling asc/desc on repeat clicks', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('columnheader', { name: /Quantity/i }));
		expect(renderedSymbols()).toEqual(['AAA', 'ZZZ', 'MMM']);

		await fireEvent.click(screen.getByRole('columnheader', { name: /Quantity/i }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);
	});

	it('does not trigger sorting when clicking or dragging column resize handles', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		// Default sort: AAA, MMM, ZZZ (total_value desc)
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);

		const handle = screen.getByTestId('column-resize-quantity');

		// Clicking the resize handle does not sort
		await fireEvent.click(handle);
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);

		// Dragging the resize handle does not sort
		await fireEvent.pointerDown(handle, { clientX: 100, pointerId: 1 });
		await fireEvent.pointerMove(handle, { clientX: 150, pointerId: 1 });
		await fireEvent.pointerUp(handle, { clientX: 150, pointerId: 1 });
		expect(renderedSymbols()).toEqual(['AAA', 'MMM', 'ZZZ']);
	});

	it('sorts null cells last in both directions', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		// Average: AAA has a null average_cost and must stay last in both directions.
		await fireEvent.click(screen.getByRole('button', { name: 'Average' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'Average' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);
	});

	it('sorts by the Return column', async () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		await fireEvent.click(screen.getByRole('button', { name: 'Return' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'Return' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);
	});

	it('sorts by EW Primary and EW Cycle columns with null/undrawn targets last in both directions', async () => {
		render(HoldingsTable, { props: { holdings: sortRows, elliottWaves: sampleElliottWaves } });

		// EW Primary: ZZZ (+100%), MMM (-50%), AAA (undrawn / null)
		await fireEvent.click(screen.getByRole('button', { name: 'EW Primary' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'EW Primary' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);

		// EW Cycle: ZZZ (+150%), MMM (+50%), AAA (undrawn / null)
		await fireEvent.click(screen.getByRole('button', { name: 'EW Cycle' }));
		expect(renderedSymbols()).toEqual(['ZZZ', 'MMM', 'AAA']);

		await fireEvent.click(screen.getByRole('button', { name: 'EW Cycle' }));
		expect(renderedSymbols()).toEqual(['MMM', 'ZZZ', 'AAA']);
	});

	it('renders one row per holding and links each security cell to /security/{id} with w-fit rounded button styling, and without underline', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		expect(screen.getAllByTestId('holding-row')).toHaveLength(3);

		const links = screen.getAllByTestId('security-link');
		expect(links[0]).toHaveAttribute('href', '/security/sec-a');
		expect(links[1]).toHaveAttribute('href', '/security/sec-m');
		expect(links[2]).toHaveAttribute('href', '/security/sec-z');

		// Check w-fit rounded button hover styling, px-2 py-1, and absence of w-full / negative margins
		for (const link of links) {
			expect(link.className).toContain('hover:bg-accent');
			expect(link.className).toContain('hover:text-accent-foreground');
			expect(link.className).toContain('w-fit');
			expect(link.className).toContain('rounded-md');
			expect(link.className).toContain('px-2');
			expect(link.className).toContain('py-1');
			expect(link.className).not.toContain('w-full');
			expect(link.className).not.toContain('-mx-1.5');
			expect(link.className).not.toContain('-my-1');
			const symbol = within(link).getByTestId('security-symbol');
			expect(symbol.className).not.toContain('group-hover:underline');
		}
	});

	it('renders account badges using Badge variant="secondary" with smaller lighter styling and a dash when blank', () => {
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
		expect(badge.className).toContain('text-[10px]');
		expect(badge.className).toContain('font-normal');
		expect(badge.className).toContain('text-muted-foreground');

		expect(cells[1]).toHaveTextContent('-');
	});

	it('renders Return column with percentage pill badge on top and dollar value underneath', () => {
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
		const posDollar = within(positiveRow).getByTestId('profit-loss');
		expect(posDollar).toHaveTextContent('+$5.00');

		const negativeRow = rowBySymbol('MMM');
		const negPill = within(negativeRow).getByTestId('profit-loss-percent');
		expect(negPill).toHaveClass('text-rose-600');
		expect(negPill).toHaveClass('inline-flex');
		expect(negPill).toHaveClass('rounded-md');
		expect(negPill).toHaveTextContent('-8.33%');
		const negDollar = within(negativeRow).getByTestId('profit-loss');
		expect(negDollar).toHaveTextContent('-$5.00');

		const zeroRow = rowBySymbol('ZERO');
		const zeroPill = within(zeroRow).getByTestId('profit-loss-percent');
		expect(zeroPill).toHaveClass('text-muted-foreground');
		expect(zeroPill).toHaveTextContent('+0.00%');
		const zeroDollar = within(zeroRow).getByTestId('profit-loss');
		expect(zeroDollar).toHaveTextContent('$0.00');
	});

	it('renders EW Primary and EW Cycle projection pill and price display with "-" fallback', () => {
		render(HoldingsTable, {
			props: {
				holdings: sortRows,
				elliottWaves: sampleElliottWaves
			}
		});

		const zRow = rowBySymbol('ZZZ');
		expect(within(zRow).getByTestId('ew-primary-upside')).toHaveTextContent('+100.00%');
		expect(within(zRow).getByTestId('ew-primary-upside')).toHaveClass('text-emerald-600');
		expect(within(zRow).getByTestId('ew-primary-target')).toHaveTextContent('$20.00');
		expect(within(zRow).getByTestId('ew-cycle-upside')).toHaveTextContent('+150.00%');
		expect(within(zRow).getByTestId('ew-cycle-upside')).toHaveClass('text-emerald-600');
		expect(within(zRow).getByTestId('ew-cycle-target')).toHaveTextContent('$25.00');

		const mRow = rowBySymbol('MMM');
		expect(within(mRow).getByTestId('ew-primary-upside')).toHaveTextContent('-50.00%');
		expect(within(mRow).getByTestId('ew-primary-upside')).toHaveClass('text-rose-600');
		expect(within(mRow).getByTestId('ew-primary-target')).toHaveTextContent('$15.00');
		expect(within(mRow).getByTestId('ew-cycle-upside')).toHaveTextContent('+50.00%');
		expect(within(mRow).getByTestId('ew-cycle-upside')).toHaveClass('text-emerald-600');
		expect(within(mRow).getByTestId('ew-cycle-target')).toHaveTextContent('$45.00');

		const aRow = rowBySymbol('AAA');
		expect(within(aRow).queryByTestId('ew-primary-upside')).not.toBeInTheDocument();
		expect(within(aRow).queryByTestId('ew-cycle-upside')).not.toBeInTheDocument();
		const aCells = within(aRow).getAllByRole('cell');
		expect(aCells[7]).toHaveTextContent('-');
		expect(aCells[8]).toHaveTextContent('-');
	});

	it('features visible separator borders on header cells and resize handles, with header hover isolation', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		const headerRow = screen.getAllByRole('row')[0];
		expect(headerRow.className).toContain('hover:bg-transparent');

		const headers = screen.getAllByRole('columnheader');
		for (const th of headers) {
			expect(th.className).toContain('border-r');
			expect(th.className).toContain('border-border/40');
			expect(th.className).toContain('transition-colors');
			expect(th.className).toContain('hover:bg-muted/50');
			expect(th.className).toContain('group/head');
			expect(th.className).toContain('cursor-pointer');
			expect(th.className).toContain('select-none');
		}

		// Verify unsorted header sort icon has group-hover/head:opacity-50
		const secHeader = screen.getByRole('columnheader', { name: /Security/i });
		const arrowIcon = secHeader.querySelector('svg');
		expect(arrowIcon).toHaveClass('opacity-0');
		expect(arrowIcon).toHaveClass('group-hover/head:opacity-50');

		const handle = screen.getByTestId('column-resize-quantity');
		expect(handle.className).toContain('border-r');
		expect(handle.className).toContain('border-border/40');
		expect(handle.className).toContain('hover:border-primary/70');
	});

	it('renders dual-currency display with CAD on top and native USD on bottom, and price and average cost in native currency only', () => {
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

		// Average: only native USD on a single line, no converted CAD line
		const avgCostCell = within(row).getAllByRole('cell')[3];
		expect(avgCostCell).toHaveTextContent('$150.00');
		expect(avgCostCell).not.toHaveTextContent('$205.00');

		// Profit / Loss: CAD primary return only, secondary unconverted USD removed
		expect(within(row).getByTestId('profit-loss')).toHaveTextContent('+$400.00');
		expect(within(row).queryByTestId('profit-loss-secondary')).not.toBeInTheDocument();

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

	it('renders "Account" column header when groupBy is null and "Accounts" when groupBy is "stock"', () => {
		const { rerender } = render(HoldingsTable, { props: { holdings: groupRows, groupBy: null } });

		expect(screen.getByRole('button', { name: 'Account' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Accounts' })).not.toBeInTheDocument();
		expect(screen.getByLabelText('Resize Account column')).toBeInTheDocument();

		rerender({ holdings: groupRows, groupBy: 'stock' });

		expect(screen.getByRole('button', { name: 'Accounts' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Account' })).not.toBeInTheDocument();
		expect(screen.getByLabelText('Resize Accounts column')).toBeInTheDocument();
	});

	it('applies zebra striping, hover, and border styling to rows and sticky Security cell', () => {
		render(HoldingsTable, { props: { holdings: groupRows, groupBy: null } });

		const rows = screen.getAllByTestId('holding-row');
		expect(rows.length).toBeGreaterThan(0);
		for (const row of rows) {
			expect(row.className).toContain('group');
			expect(row.className).toContain('border-b');
			expect(row.className).toContain('border-border');
			expect(row.className).toContain('even:bg-muted/50');
			expect(row.className).toContain('hover:bg-muted/80');
		}

		// Sticky Security cell on each row matches even zebra striping, hover background, and border
		const securityCells = rows.map((r) => within(r).getByTestId('security-symbol').closest('td')!);
		for (const cell of securityCells) {
			expect(cell.className).toContain('sticky');
			expect(cell.className).toContain('left-0');
			expect(cell.className).toContain('bg-background');
			expect(cell.className).toContain('group-even:bg-muted/50');
			expect(cell.className).toContain('group-hover:bg-muted/80');
			expect(cell.className).toContain('group-even:group-hover:bg-muted/80');
			expect(cell.className).toContain('border-r');
			expect(cell.className).toContain('border-border/40');
		}

		// All cells across the row have softened column border-r border-border/40
		const firstRow = rows[0];
		const cells = within(firstRow).getAllByRole('cell');
		for (const cell of cells) {
			expect(cell.className).toContain('border-r');
			expect(cell.className).toContain('border-border/40');
		}
	});

	it('renders Quantity cell with text-xs tabular-nums typography matching numeric columns', () => {
		render(HoldingsTable, { props: { holdings: sortRows } });

		const row = rowBySymbol('ZZZ');
		const cells = within(row).getAllByRole('cell');
		// Index 2 is Quantity
		const quantityCell = cells[2];
		expect(quantityCell.className).toContain('text-xs');
		expect(quantityCell.className).toContain('tabular-nums');
		expect(quantityCell.className).not.toContain('text-sm');
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
			expect(onConfigChange.mock.calls[0][0].visible).toEqual([...HOLDINGS_TABLE_COLUMN_IDS]);
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

		it('shrinks the empty-state colspan to the number of visible columns in tableConfig', () => {
			const tableConfig = normalizeHoldingsTableConfig({
				visible: ['security_symbol', 'quantity', 'total_value']
			});

			render(HoldingsTable, { props: { holdings: [], tableConfig } });

			expect(screen.getByTestId('empty-state').querySelector('td')).toHaveAttribute('colspan', '3');
		});

		it('falls back to the defaults for an invalid stored config', () => {
			const tableConfig = {
				widths: { quantity: 10_000, unknown: 50 },
				visible: ['not_a_column']
			} as unknown as HoldingsTableConfig;

			render(HoldingsTable, { props: { holdings: sortRows, tableConfig } });

			expect(screen.getAllByRole('columnheader')).toHaveLength(9);
			expect(screen.getByTestId('column-col-quantity').style.width).toBe('180px');
		});
	});
});
