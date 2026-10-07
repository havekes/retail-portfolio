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
