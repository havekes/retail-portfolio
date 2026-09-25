import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { Portfolio } from '$lib/types/portfolio';
import { AccountType, Institution } from '$lib/types/account';
import type { PageData } from './$types';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

describe('/portfolios +page.svelte', () => {
	const mockPortfolios: Portfolio[] = [
		{
			id: 'port-1',
			name: 'Tech Growth',
			created_at: '2025-06-15T12:00:00Z',
			accounts: [
				{
					id: 'acc-1',
					name: 'TFSA',
					external_id: 'ext-1',
					account_type_id: AccountType.TFSA,
					institution_id: Institution.Questrade,
					currency: 'CAD',
					is_active: true,
					api_sync_enabled: false,
					created_at: new Date('2025-01-01')
				}
			]
		},
		{
			id: 'port-2',
			name: 'Retirement Fund',
			created_at: '2024-01-10T10:00:00Z',
			accounts: [
				{
					id: 'acc-2',
					name: 'RRSP',
					external_id: 'ext-2',
					account_type_id: AccountType.RRSP,
					institution_id: Institution.Questrade,
					currency: 'CAD',
					is_active: true,
					api_sync_enabled: false,
					created_at: new Date('2024-01-01')
				},
				{
					id: 'acc-3',
					name: 'LIRA',
					external_id: 'ext-3',
					account_type_id: AccountType.RRSP,
					institution_id: Institution.Wealthsimple,
					currency: 'CAD',
					is_active: true,
					api_sync_enabled: false,
					created_at: new Date('2024-01-01')
				}
			]
		}
	];

	function makeData(overrides: Partial<PageData> = {}): PageData {
		return {
			user: { id: 'u1', email: 'test@example.com' },
			sidebar_open: true,
			collapsed_watchlist_ids: [],
			watchlist_order: null,
			portfolios: mockPortfolios,
			...overrides
		};
	}

	it('renders portfolios with name, account count, and formatted created date', () => {
		render(Page, {
			props: {
				data: makeData()
			}
		});

		expect(screen.getByText('Portfolios')).toBeInTheDocument();
		expect(screen.getByText('Tech Growth')).toBeInTheDocument();
		expect(screen.getByText('1 account')).toBeInTheDocument();
		expect(screen.getByText('Created Jun 15, 2025')).toBeInTheDocument();

		expect(screen.getByText('Retirement Fund')).toBeInTheDocument();
		expect(screen.getByText('2 accounts')).toBeInTheDocument();
		expect(screen.getByText('Created Jan 10, 2024')).toBeInTheDocument();
	});

	it('renders empty state when there are no portfolios', () => {
		render(Page, {
			props: {
				data: makeData({ portfolios: [] })
			}
		});

		expect(screen.getByTestId('empty-state')).toBeInTheDocument();
		expect(screen.getByText("You don't have any portfolios yet")).toBeInTheDocument();
	});

	it('links each portfolio card to /holdings?portfolio_id=<id>', () => {
		render(Page, {
			props: {
				data: makeData()
			}
		});

		const card1 = screen.getByTestId('portfolio-card-port-1');
		expect(card1).toHaveAttribute('href', '/holdings?portfolio_id=port-1');

		const card2 = screen.getByTestId('portfolio-card-port-2');
		expect(card2).toHaveAttribute('href', '/holdings?portfolio_id=port-2');
	});
});
