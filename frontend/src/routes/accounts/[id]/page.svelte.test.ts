import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { AccountHoldings } from '$lib/types/account';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/forms', () => ({
	enhance: () => () => {}
}));

function makeHoldings(overrides: Partial<AccountHoldings> = {}): AccountHoldings {
	return {
		account_id: 'acc-1',
		account_name: 'My Test Account',
		total_value: 1000,
		total_profit_loss: 100,
		total_profit_loss_percent: 10,
		profit_loss_basis: 'net_deposits',
		net_deposits: 900,
		currency: 'CAD',
		items: [],
		total: 0,
		offset: 0,
		limit: 50,
		...overrides
	};
}

function renderPage(holdings: AccountHoldings) {
	// The route page only reads `data.holdings`; the full PageData shape is not needed here.
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	return render(Page, { props: { data: { holdings } as any } });
}

describe('/accounts/[id] +page.svelte incomplete pricing warning (ARCH-T26)', () => {
	it('shows the warning icon when pricing_incomplete is true', async () => {
		renderPage(makeHoldings({ unpriced_positions: 1, pricing_incomplete: true }));

		expect(await screen.findByLabelText('Incomplete pricing')).toBeInTheDocument();
	});

	it('does not show the warning icon when pricing_incomplete is false', () => {
		renderPage(makeHoldings({ unpriced_positions: 0, pricing_incomplete: false }));

		expect(screen.queryByLabelText('Incomplete pricing')).not.toBeInTheDocument();
	});
});

describe('/accounts/[id] +page.svelte header totals (ARCH-T30)', () => {
	it('renders the total value and profit/loss buttons instead of the labelled stat columns', () => {
		renderPage(makeHoldings());

		expect(screen.getByTestId('total-value-btn')).toHaveTextContent('$1,000.00');
		expect(screen.getByTestId('profit-loss-btn')).toHaveTextContent('+10.00%');
		expect(screen.getByTestId('profit-loss-btn')).toHaveTextContent('+$100.00');

		expect(screen.queryByText('Total Value')).not.toBeInTheDocument();
		expect(screen.queryByText('Net Deposits')).not.toBeInTheDocument();
		expect(screen.queryByText('Total P/L')).not.toBeInTheDocument();
	});
});
