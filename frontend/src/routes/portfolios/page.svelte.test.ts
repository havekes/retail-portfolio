import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { Portfolio } from '$lib/types/portfolio';
import { AccountType, Institution } from '$lib/types/account';
import type { PageData } from './$types';
import { portfolioClient } from '$lib/api/portfolioClient';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$lib/api/portfolioClient', () => ({
	portfolioClient: {
		updatePortfolio: vi.fn(),
		deletePortfolio: vi.fn()
	},
	getPortfolioClient: vi.fn()
}));

describe('/portfolios +page.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	function getMockPortfolios(): Portfolio[] {
		return [
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
	}

	function makeData(overrides: Partial<PageData> = {}): PageData {
		return {
			user: { id: 'u1', email: 'test@example.com' },
			sidebar_open: true,
			collapsed_watchlist_ids: [],
			watchlist_order: null,
			expanded_account_ids: [],
			portfolios: getMockPortfolios(),
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

	it('links each portfolio title to /holdings?portfolio_id=<id>', () => {
		render(Page, {
			props: {
				data: makeData()
			}
		});

		const link1 = screen.getByRole('link', { name: 'Tech Growth' });
		expect(link1).toHaveAttribute('href', '/holdings?portfolio_id=port-1');

		const link2 = screen.getByRole('link', { name: 'Retirement Fund' });
		expect(link2).toHaveAttribute('href', '/holdings?portfolio_id=port-2');
	});

	it('triggers inline rename from dropdown and updates portfolio name upon saving', async () => {
		vi.mocked(portfolioClient.updatePortfolio).mockResolvedValue({
			id: 'port-1',
			name: 'Tech Growth 2026',
			accounts: []
		});

		render(Page, {
			props: {
				data: makeData()
			}
		});

		const menuButtons = screen.getAllByRole('button', { name: 'Portfolio actions' });
		await fireEvent.click(menuButtons[0]);

		const renameOption = await screen.findByRole('menuitem', { name: /Rename/i });
		await fireEvent.click(renameOption);

		const input = await screen.findByDisplayValue('Tech Growth');
		await fireEvent.input(input, { target: { value: 'Tech Growth 2026' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		await waitFor(() => {
			expect(portfolioClient.updatePortfolio).toHaveBeenCalledWith('port-1', {
				name: 'Tech Growth 2026'
			});
		});

		expect(await screen.findByText('Tech Growth 2026')).toBeInTheDocument();
	});

	it('opens delete confirmation modal and removes portfolio upon confirmation', async () => {
		vi.mocked(portfolioClient.deletePortfolio).mockResolvedValue(undefined);

		render(Page, {
			props: {
				data: makeData()
			}
		});

		const menuButtons = screen.getAllByRole('button', { name: 'Portfolio actions' });
		await fireEvent.click(menuButtons[0]);

		const deleteOption = await screen.findByRole('menuitem', { name: /Delete portfolio/i });
		await fireEvent.click(deleteOption);

		expect(await screen.findByText('Delete portfolio')).toBeInTheDocument();
		expect(
			screen.getByText(
				'Are you sure you want to delete "Tech Growth"? This action cannot be undone.'
			)
		).toBeInTheDocument();

		const confirmButton = screen.getByRole('button', { name: 'Confirm' });
		await fireEvent.click(confirmButton);

		await waitFor(() => {
			expect(portfolioClient.deletePortfolio).toHaveBeenCalledWith('port-1');
		});

		await waitFor(() => {
			expect(screen.queryByText('Tech Growth')).not.toBeInTheDocument();
		});
		expect(screen.getByText('Retirement Fund')).toBeInTheDocument();
	});

	it('cancels delete confirmation modal without deleting portfolio', async () => {
		render(Page, {
			props: {
				data: makeData()
			}
		});

		const menuButtons = screen.getAllByRole('button', { name: 'Portfolio actions' });
		await fireEvent.click(menuButtons[0]);

		const deleteOption = await screen.findByRole('menuitem', { name: /Delete portfolio/i });
		await fireEvent.click(deleteOption);

		expect(await screen.findByText('Delete portfolio')).toBeInTheDocument();

		const cancelButton = screen.getByRole('button', { name: 'Cancel' });
		await fireEvent.click(cancelButton);

		expect(portfolioClient.deletePortfolio).not.toHaveBeenCalled();
		expect(screen.getByText('Tech Growth')).toBeInTheDocument();
	});
});
