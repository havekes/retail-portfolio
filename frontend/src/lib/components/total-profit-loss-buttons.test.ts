import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import TotalProfitLossButtons from './total-profit-loss-buttons.svelte';

describe('TotalProfitLossButtons', () => {
	it('renders two distinct outline buttons for total value and profit/loss', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1250.5,
				profitLoss: 250.5,
				returnPercent: 25,
				currency: 'CAD'
			}
		});

		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(2);
		expect(screen.getByText('$1,250.50')).toBeInTheDocument();
		expect(screen.getByText('+25.00%')).toBeInTheDocument();
		expect(screen.getByText('+$250.50')).toBeInTheDocument();
	});

	it('accepts Money object for totalValue and costBasis', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: { value: '100', units: 100, nanos: 0, currencyCode: 'CAD' },
				costBasis: { value: '80', units: 80, nanos: 0, currencyCode: 'CAD' }
			}
		});

		expect(screen.getByText('$100.00')).toBeInTheDocument();
		// profitLoss should be calculated as 20, returnPercent as 25%
		expect(screen.getByText('+$20.00')).toBeInTheDocument();
		expect(screen.getByText('+25.00%')).toBeInTheDocument();
	});

	it('applies emerald styling for positive profit/loss and return percent', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 500,
				profitLoss: 50,
				returnPercent: 11.11,
				currency: 'CAD'
			}
		});

		const percentEl = screen.getByText('+11.11%');
		const plValueEl = screen.getByText('+$50.00');

		expect(percentEl).toHaveClass('text-emerald-600');
		expect(plValueEl).toHaveClass('text-emerald-600');
	});

	it('applies rose styling for negative profit/loss and return percent', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 400,
				profitLoss: -100,
				returnPercent: -20,
				currency: 'CAD'
			}
		});

		const percentEl = screen.getByText('-20.00%');
		const plValueEl = screen.getByText('-$100.00');

		expect(percentEl).toHaveClass('text-rose-600');
		expect(plValueEl).toHaveClass('text-rose-600');
	});

	it('renders smaller font size for P/L value when percent is displayed', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				profitLoss: 100,
				returnPercent: 11.11
			}
		});

		const plValueEl = screen.getByText('+$100.00');
		expect(plValueEl).toHaveClass('text-xs');
	});

	it('supports testIdPrefix for targeting individual elements', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				profitLoss: 50,
				returnPercent: 5.26,
				testIdPrefix: 'account-1'
			}
		});

		expect(screen.getByTestId('account-1-total-value')).toBeInTheDocument();
		expect(screen.getByTestId('account-1-profit-loss')).toBeInTheDocument();
		expect(screen.getByTestId('account-1-return-percent')).toBeInTheDocument();
		expect(screen.getByTestId('account-1-profit-loss-value')).toBeInTheDocument();
	});

	it('renders without tooltips when showTooltip is false', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				profitLoss: 50,
				showTooltip: false
			}
		});

		const buttons = screen.getAllByRole('button');
		expect(buttons).toHaveLength(2);
		expect(screen.getByText('$1,000.00')).toBeInTheDocument();
		expect(screen.getByText('+$50.00')).toBeInTheDocument();
	});

	it('treats an explicit null returnPercent as "no percent" instead of deriving one', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				costBasis: 800,
				profitLoss: 200,
				returnPercent: null
			}
		});

		expect(screen.getByText('+$200.00')).toBeInTheDocument();
		expect(screen.queryByText('+25.00%')).not.toBeInTheDocument();
	});

	it('still derives the return percent when returnPercent is omitted', () => {
		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				costBasis: 800,
				profitLoss: 200
			}
		});

		expect(screen.getByText('+25.00%')).toBeInTheDocument();
	});

	it('shows the basis label in the profit/loss tooltip', async () => {
		const user = userEvent.setup();

		render(TotalProfitLossButtons, {
			props: {
				totalValue: 1000,
				profitLoss: 50,
				returnPercent: 5.26,
				basisLabel: 'mixed basis',
				testIdPrefix: 'account-1'
			}
		});

		expect(screen.queryByText('mixed basis')).not.toBeInTheDocument();

		await user.hover(screen.getByTestId('account-1-profit-loss'));

		expect(await screen.findByText('mixed basis')).toBeInTheDocument();
	});
});
