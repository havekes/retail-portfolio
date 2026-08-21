import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import HoldingGroup from './holding-group.svelte';
import type { AccountHoldingRead } from '$lib/api/accountService';
import type { Candle } from '$lib/utils/finance/candle';
import type { SecuritySchema } from '$lib/api/marketService';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$lib/api/accountService', () => ({
	accountService: {
		getHoldings: vi.fn()
	}
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		getPreferences: vi.fn(),
		patchPreferences: vi.fn()
	}
}));

import { accountService } from '$lib/api/accountService';
import { userPreferencesService } from '$lib/api/userPreferencesService';

describe('HoldingGroup Component', () => {
	const mockSecurity: SecuritySchema = {
		id: 'sec-123',
		symbol: 'AAPL',
		name: 'Apple Inc.',
		currency: 'USD',
		exchange: 'NASDAQ',
		isin: 'US0378331005',
		is_active: true,
		updated_at: '2026-08-20T00:00:00Z'
	};

	const mockHoldings: AccountHoldingRead[] = [
		{
			account_id: 'acc-1',
			account_name: 'Tax-Free Savings',
			quantity: 10,
			average_cost: 100,
			total_value: 1500,
			currency: 'USD',
			account_percentage: 25.5
		},
		{
			account_id: 'acc-2',
			account_name: 'Non-Registered',
			quantity: 20,
			average_cost: 120,
			total_value: 3000,
			currency: 'USD',
			account_percentage: 45.0
		}
	];

	const mockCandles: Candle[] = [
		{
			time: '2026-08-19',
			open: 140,
			high: 145,
			low: 138,
			close: 140,
			volume: 15000
		},
		{
			time: '2026-08-20',
			open: 148,
			high: 152,
			low: 147,
			close: 150,
			volume: 20000
		}
	];

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			holdings_period: 'ALL'
		});
		vi.mocked(userPreferencesService.patchPreferences).mockResolvedValue({});
		vi.mocked(accountService.getHoldings).mockResolvedValue({
			items: mockHoldings,
			total: 2,
			offset: 0,
			limit: 10
		});
	});

	describe('Header & Expand Action Trigger', () => {
		it('renders Your Holdings header and expand button with proper title/aria-label', async () => {
			render(HoldingGroup, {
				props: {
					securityId: 'sec-123',
					security: mockSecurity,
					candles: mockCandles
				}
			});

			expect(screen.getByText('Your Holdings')).toBeInTheDocument();
			const expandButton = screen.getByRole('button', { name: 'Expand holdings breakdown' });
			expect(expandButton).toBeInTheDocument();
			expect(expandButton).toHaveAttribute('title', 'Expand holdings breakdown');
		});

		it('opens HoldingsModal when expand action button is clicked', async () => {
			render(HoldingGroup, {
				props: {
					securityId: 'sec-123',
					security: mockSecurity,
					candles: mockCandles
				}
			});

			const expandButton = screen.getByRole('button', { name: 'Expand holdings breakdown' });
			await fireEvent.click(expandButton);

			await waitFor(() => {
				expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
				expect(screen.getByText('AAPL · Apple Inc.')).toBeInTheDocument();
			});
		});

		it('forwards security details and candles to the modal dialog', async () => {
			render(HoldingGroup, {
				props: {
					securityId: 'sec-123',
					security: mockSecurity,
					candles: mockCandles
				}
			});

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
			});

			const expandButton = screen.getByRole('button', { name: 'Expand holdings breakdown' });
			await fireEvent.click(expandButton);

			await waitFor(() => {
				expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
				expect(screen.getByText('AAPL · Apple Inc.')).toBeInTheDocument();
				expect(
					screen.getAllByRole('img', { name: 'Price sparkline' }).length
				).toBeGreaterThanOrEqual(1);
			});
		});
	});

	describe('Collapse and expand toggle', () => {
		it('collapses and expands sidebar list when title is clicked without affecting modal', async () => {
			render(HoldingGroup, {
				props: {
					securityId: 'sec-123',
					security: mockSecurity,
					candles: mockCandles
				}
			});

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
			});

			// Click toggle button on header to collapse
			const toggleButton = screen.getByText('Your Holdings');
			await fireEvent.click(toggleButton);

			// Sidebar content is collapsed
			expect(screen.queryByText('Tax-Free Savings')).not.toBeInTheDocument();

			// Click expand button to open modal while sidebar is collapsed
			const expandButton = screen.getByRole('button', { name: 'Expand holdings breakdown' });
			await fireEvent.click(expandButton);

			await waitFor(() => {
				expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
			});

			// Re-expand sidebar while modal is open
			await fireEvent.click(toggleButton);

			// Both modal and sidebar content exist
			expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
			expect(screen.getAllByText('Tax-Free Savings').length).toBe(2);

			// Collapse sidebar again - modal stays open
			await fireEvent.click(toggleButton);
			expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
			expect(screen.getAllByText('Tax-Free Savings').length).toBe(1); // inside modal only
		});
	});

	describe('Holdings List rendering', () => {
		it('renders holdings accounts, quantities, values, and portfolio avg', async () => {
			render(HoldingGroup, {
				props: {
					securityId: 'sec-123',
					security: mockSecurity
				}
			});

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
				expect(screen.getByText('Non-Registered')).toBeInTheDocument();
			});

			expect(screen.getByText('$1,500.00')).toBeInTheDocument();
			expect(screen.getByText('$3,000.00')).toBeInTheDocument();
			expect(screen.getByText('10 shares · Avg $100.00')).toBeInTheDocument();
			expect(screen.getByText('20 shares · Avg $120.00')).toBeInTheDocument();
			expect(screen.getByText('Portfolio avg')).toBeInTheDocument();
			expect(screen.getByText('$113.33')).toBeInTheDocument();

			const link1 = screen.getByRole('link', { name: /Tax-Free Savings/ });
			expect(link1).toHaveAttribute('href', '/accounts/acc-1');
		});
	});

	describe('Loading, empty, and error states', () => {
		it('shows loading state while fetching holdings', () => {
			vi.mocked(accountService.getHoldings).mockReturnValue(new Promise(() => {}));

			render(HoldingGroup, {
				props: {
					securityId: 'sec-123'
				}
			});

			expect(screen.queryByText('Tax-Free Savings')).not.toBeInTheDocument();
		});

		it('shows empty message when user has no holdings', async () => {
			vi.mocked(accountService.getHoldings).mockResolvedValue({
				items: [],
				total: 0,
				offset: 0,
				limit: 10
			});

			render(HoldingGroup, {
				props: {
					securityId: 'sec-123'
				}
			});

			await waitFor(() => {
				expect(screen.getByText("You don't hold any shares of this security.")).toBeInTheDocument();
			});
		});

		it('shows error state on failure and retries on retry button click', async () => {
			const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
			vi.mocked(accountService.getHoldings).mockRejectedValueOnce(new Error('Network failure'));

			render(HoldingGroup, {
				props: {
					securityId: 'sec-123'
				}
			});

			await waitFor(() => {
				expect(screen.getByText('Failed to load holdings')).toBeInTheDocument();
			});

			const retryBtn = screen.getByRole('button', { name: /try again/i });
			expect(retryBtn).toBeInTheDocument();

			vi.mocked(accountService.getHoldings).mockResolvedValueOnce({
				items: mockHoldings,
				total: 2,
				offset: 0,
				limit: 10
			});

			await fireEvent.click(retryBtn);

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
			});
			errorSpy.mockRestore();
		});
	});
});
