import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import AccountInlineHoldings from './account-inline-holdings.svelte';
import type { Holding } from '@/types/account';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

describe('AccountInlineHoldings', () => {
	const sampleHoldings: Holding[] = [
		{
			id: 'h-pos',
			security_id: 'sec-1',
			security_symbol: 'TD',
			security_name: 'Toronto-Dominion Bank',
			quantity: 50,
			average_cost: 80,
			total_value: 4500,
			profit_loss: 500,
			currency: 'CAD',
			display_total_value: 4500,
			display_currency: 'CAD',
			security_currency: 'CAD',
			unconverted_total_value: 4500,
			converted_average_cost: 80,
			converted_latest_price: 90,
			unconverted_profit_loss: 500,
			latest_price: 90
		},
		{
			id: 'h-neg',
			security_id: 'sec-2',
			security_symbol: 'BNS',
			security_name: 'Bank of Nova Scotia',
			quantity: 25,
			average_cost: 70,
			total_value: 1500,
			profit_loss: -250,
			currency: 'CAD',
			display_total_value: 1500,
			display_currency: 'CAD',
			security_currency: 'CAD',
			unconverted_total_value: 1500,
			converted_average_cost: 70,
			converted_latest_price: 60,
			unconverted_profit_loss: -250,
			latest_price: 60
		},
		{
			id: 'h-null-price',
			security_id: 'sec-3',
			security_symbol: 'CASH',
			security_name: 'Horizons High Interest Savings ETF',
			quantity: 100,
			average_cost: 50,
			total_value: 5000,
			profit_loss: null,
			currency: 'CAD',
			display_total_value: 5000,
			display_currency: 'CAD',
			security_currency: 'CAD',
			unconverted_total_value: 5000,
			converted_average_cost: 50,
			converted_latest_price: null,
			unconverted_profit_loss: null,
			latest_price: undefined
		}
	];

	it('renders table headers Symbol, Account Value, Price, and Return', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		expect(screen.getByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();
		expect(screen.getByRole('columnheader', { name: 'Account Value' })).toBeInTheDocument();
		expect(screen.getByRole('columnheader', { name: 'Price' })).toBeInTheDocument();
		expect(screen.getByRole('columnheader', { name: 'Return' })).toBeInTheDocument();
		expect(screen.queryByRole('columnheader', { name: 'Quantity' })).not.toBeInTheDocument();
		expect(screen.queryByRole('columnheader', { name: 'Total Value' })).not.toBeInTheDocument();
	});

	it('renders Account Value with formatCurrency for each holding', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		expect(screen.getByText('$4,500.00')).toBeInTheDocument();
		expect(screen.getByText('$1,500.00')).toBeInTheDocument();
		expect(screen.getByText('$5,000.00')).toBeInTheDocument();
	});

	it('renders symbols and links to /security/[id]', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		const tdLink = screen.getByText('TD').closest('a');
		expect(tdLink).toHaveAttribute('href', '/security/sec-1');
		expect(screen.getByText('Toronto-Dominion Bank')).toBeInTheDocument();

		const bnsLink = screen.getByText('BNS').closest('a');
		expect(bnsLink).toHaveAttribute('href', '/security/sec-2');
	});

	it('renders return percentage pill and signed currency amount', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		// TD: positive return (+12.50% pill, +$500.00 currency below)
		const tdPill = screen.getByText('+12.50%');
		expect(tdPill).toBeInTheDocument();
		expect(tdPill).toHaveClass('text-emerald-600');
		expect(screen.getByText(/\+\$500\.00/)).toBeInTheDocument();

		// BNS: negative return (-14.29% pill, -$250.00 currency below)
		const bnsPill = screen.getByText('-14.29%');
		expect(bnsPill).toBeInTheDocument();
		expect(bnsPill).toHaveClass('text-rose-600');
		expect(screen.getByText(/-\$250\.00/)).toBeInTheDocument();
	});

	it('renders dash (-) when latest_price or profit_loss is null/undefined', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: [sampleHoldings[2]],
				accountCurrency: 'CAD'
			}
		});

		const dashes = screen.getAllByText('-');
		// Price is null -> '-', Return is null -> '-'
		expect(dashes.length).toBeGreaterThanOrEqual(2);
	});

	it('renders empty message when holdings list is empty', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: [],
				accountCurrency: 'CAD'
			}
		});

		expect(screen.getByText('No holdings found for this account.')).toBeInTheDocument();
	});

	it('renders security symbol/name links with rounded hover background classes, dark hover classes, and uniform full width', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		const tdLink = screen.getByText('TD').closest('a');
		expect(tdLink).toHaveClass('rounded-md');
		expect(tdLink).toHaveClass('hover:bg-background/60');
		expect(tdLink).toHaveClass('dark:hover:bg-background/60');
		expect(tdLink).toHaveClass('w-full');
		expect(tdLink).not.toHaveClass('w-fit');

		const bnsLink = screen.getByText('BNS').closest('a');
		expect(bnsLink).toHaveClass('w-full');
		expect(bnsLink).not.toHaveClass('w-fit');
	});

	it('renders security symbol without hover underline', () => {
		render(AccountInlineHoldings, {
			props: {
				holdings: sampleHoldings,
				accountCurrency: 'CAD'
			}
		});

		const tdSymbol = screen.getByText('TD');
		expect(tdSymbol).not.toHaveClass('group-hover:underline');
		expect(tdSymbol).not.toHaveClass('underline');
	});
});
