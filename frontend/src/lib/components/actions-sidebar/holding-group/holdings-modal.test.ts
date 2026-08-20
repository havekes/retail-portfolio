import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import HoldingsModal from './holdings-modal.svelte';
import { ModalState } from '$lib/utils/modal-state.svelte';
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

describe('HoldingsModal Component', () => {
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
			time: '2025-01-01',
			open: 90,
			high: 95,
			low: 85,
			close: 90,
			volume: 10000
		},
		{
			time: '2026-01-01',
			open: 110,
			high: 115,
			low: 105,
			close: 110,
			volume: 12000
		},
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

	describe('Dialog accessibility & open/close', () => {
		it('renders dialog content when open with modalState', () => {
			const modalState = new ModalState<SecuritySchema>();
			modalState.open(mockSecurity);

			render(HoldingsModal, {
				props: {
					modalState,
					holdings: mockHoldings,
					candles: mockCandles
				}
			});

			expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
			expect(screen.getByText('AAPL · Apple Inc.')).toBeInTheDocument();
		});

		it('renders dialog content when open with open prop', () => {
			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles
				}
			});

			expect(screen.getByText('Holdings Breakdown')).toBeInTheDocument();
			expect(screen.getByText('AAPL · Apple Inc.')).toBeInTheDocument();
		});

		it('closes dialog when Close button is clicked', async () => {
			const modalState = new ModalState<SecuritySchema>();
			modalState.open(mockSecurity);

			render(HoldingsModal, {
				props: {
					modalState,
					holdings: mockHoldings,
					candles: mockCandles
				}
			});

			const closeButtons = screen.getAllByRole('button', { name: 'Close' });
			expect(closeButtons.length).toBeGreaterThanOrEqual(1);
			await fireEvent.click(closeButtons[0]);

			expect(modalState.isOpen).toBe(false);
		});
	});

	describe('Table columns and data rendering', () => {
		it('renders all 7 table columns with proper formats and links', () => {
			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles,
					currentPrice: 150
				}
			});

			// Headers
			expect(screen.getByRole('columnheader', { name: 'Account' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Shares' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Avg Price' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Total Value' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: '% of Account' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Period Gain' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Trend' })).toBeInTheDocument();

			// Row 1 Account Link
			const link1 = screen.getByRole('link', { name: 'Tax-Free Savings' });
			expect(link1).toHaveAttribute('href', '/accounts/acc-1');

			// Row 2 Account Link
			const link2 = screen.getByRole('link', { name: 'Non-Registered' });
			expect(link2).toHaveAttribute('href', '/accounts/acc-2');

			// Shares
			expect(screen.getByText('10')).toBeInTheDocument();
			expect(screen.getByText('20')).toBeInTheDocument();

			// Avg Price
			expect(screen.getByText('$100.00')).toBeInTheDocument();
			expect(screen.getByText('$120.00')).toBeInTheDocument();

			// Total Value
			expect(screen.getByText('$1,500.00')).toBeInTheDocument();
			expect(screen.getByText('$3,000.00')).toBeInTheDocument();

			// Account %
			expect(screen.getByText('25.50%')).toBeInTheDocument();
			expect(screen.getByText('45.00%')).toBeInTheDocument();

			// Gain (ALL period against cost basis: 150 - 100 = 50 * 10 = $500, +50.00%)
			expect(screen.getByText('+$500.00')).toBeInTheDocument();
			expect(screen.getByText('+50.00%')).toBeInTheDocument();

			// Gain (Row 2: 150 - 120 = 30 * 20 = $600, +25.00%)
			expect(screen.getByText('+$600.00')).toBeInTheDocument();
			expect(screen.getByText('+25.00%')).toBeInTheDocument();

			// Sparklines
			const sparklines = screen.getAllByRole('img', { name: 'Price sparkline' });
			expect(sparklines.length).toBe(2);
		});
	});

	describe('Period switching & dynamic recalculations', () => {
		it('renders all period buttons and switches active period on click', async () => {
			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles,
					currentPrice: 150
				}
			});

			const periods = ['1D', '1W', '1M', '1Y', 'YTD', 'ALL'];
			for (const p of periods) {
				expect(screen.getByRole('button', { name: p })).toBeInTheDocument();
			}

			// Click '1D' button
			const oneDayButton = screen.getByRole('button', { name: '1D' });
			await fireEvent.click(oneDayButton);

			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				holdings_period: '1D'
			});

			expect(oneDayButton).toHaveAttribute('aria-pressed', 'true');
		});

		it('recalculates gain metrics when period changes', async () => {
			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles,
					currentPrice: 150
				}
			});

			const oneDayButton = screen.getByRole('button', { name: '1D' });
			await fireEvent.click(oneDayButton);

			await waitFor(() => {
				expect(screen.getByText('+$100.00')).toBeInTheDocument();
				expect(screen.getAllByText('+7.14%').length).toBeGreaterThanOrEqual(1);
			});
		});
	});

	describe('Preference management', () => {
		it('loads saved holdings_period on open', async () => {
			vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
				holdings_period: '1M'
			});

			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles
				}
			});

			await waitFor(() => {
				const oneMonthButton = screen.getByRole('button', { name: '1M' });
				expect(oneMonthButton).toHaveAttribute('aria-pressed', 'true');
			});
		});

		it('falls back to ALL if preference is missing or invalid', async () => {
			vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
				holdings_period: 'INVALID_PERIOD'
			});

			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles
				}
			});

			await waitFor(() => {
				const allButton = screen.getByRole('button', { name: 'ALL' });
				expect(allButton).toHaveAttribute('aria-pressed', 'true');
			});
		});
	});

	describe('Summary footer calculations', () => {
		it('correctly aggregates shares, blended average price, total value, and gain', () => {
			render(HoldingsModal, {
				props: {
					open: true,
					security: mockSecurity,
					holdings: mockHoldings,
					candles: mockCandles,
					currentPrice: 150
				}
			});

			// Total Shares: 10 + 20 = 30
			expect(screen.getByText('30')).toBeInTheDocument();

			// Portfolio Avg: (10*100 + 20*120)/30 = 3400/30 = 113.33 -> $113.33
			expect(screen.getByText('$113.33')).toBeInTheDocument();

			// Total Value: 1500 + 3000 = $4,500.00
			expect(screen.getByText('$4,500.00')).toBeInTheDocument();

			// Aggregated Gain: $500 + $600 = $1,100.00 (+32.35%)
			expect(screen.getByText('+$1,100.00')).toBeInTheDocument();
			expect(screen.getByText('+32.35%')).toBeInTheDocument();
		});
	});

	describe('Data fetching & states', () => {
		it('fetches holdings from accountService when not supplied via props', async () => {
			render(HoldingsModal, {
				props: {
					open: true,
					securityId: 'sec-123',
					candles: mockCandles
				}
			});

			expect(accountService.getHoldings).toHaveBeenCalledWith('sec-123');

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
				expect(screen.getByText('Non-Registered')).toBeInTheDocument();
			});
		});

		it('shows loading skeleton while fetching', () => {
			// Delay promise resolution
			vi.mocked(accountService.getHoldings).mockReturnValue(new Promise(() => {}));

			render(HoldingsModal, {
				props: {
					open: true,
					securityId: 'sec-123'
				}
			});

			expect(screen.getByTestId('holdings-loading-skeleton')).toBeInTheDocument();
		});

		it('shows empty state when no holdings are returned', async () => {
			vi.mocked(accountService.getHoldings).mockResolvedValue({
				items: [],
				total: 0,
				offset: 0,
				limit: 10
			});

			render(HoldingsModal, {
				props: {
					open: true,
					securityId: 'sec-123'
				}
			});

			await waitFor(() => {
				expect(screen.getByText('No holdings found for this security.')).toBeInTheDocument();
			});
		});

		it('shows error state with retry button on API failure and retries on click', async () => {
			vi.mocked(accountService.getHoldings).mockRejectedValueOnce(new Error('Network error'));

			render(HoldingsModal, {
				props: {
					open: true,
					securityId: 'sec-123'
				}
			});

			await waitFor(() => {
				expect(screen.getByText('Network error')).toBeInTheDocument();
			});

			const retryButton = screen.getByRole('button', { name: 'Retry' });
			expect(retryButton).toBeInTheDocument();

			vi.mocked(accountService.getHoldings).mockResolvedValueOnce({
				items: mockHoldings,
				total: 2,
				offset: 0,
				limit: 10
			});

			await fireEvent.click(retryButton);

			await waitFor(() => {
				expect(screen.getByText('Tax-Free Savings')).toBeInTheDocument();
			});
		});
	});
});
