import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import WatchlistSecurityPicker from './watchlist-security-picker.svelte';
import type { MarketSearchResult } from '@/api/marketService';
import type { WatchlistService } from './watchlistService.svelte';

const mocks = vi.hoisted(() => ({
	service: null as unknown as WatchlistService
}));

vi.mock('$lib/components/watchlist/watchlistService.svelte', async (importOriginal) => {
	const actual =
		await importOriginal<typeof import('$lib/components/watchlist/watchlistService.svelte')>();
	return {
		...actual,
		getWatchlistService: () => mocks.service
	};
});

describe('WatchlistSecurityPicker component', () => {
	let mockSearchSecurities: ReturnType<typeof vi.fn>;
	let mockAddSecurity: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		vi.resetAllMocks();
		mockSearchSecurities = vi.fn();
		mockAddSecurity = vi.fn();
		mocks.service = {
			searchSecurities: mockSearchSecurities,
			addSecurity: mockAddSecurity,
			error: null
		} as unknown as WatchlistService;
	});

	it('preserves latest search results when two queries resolve out of order', async () => {
		let resolveFirst: (results: MarketSearchResult[]) => void = () => {};
		let resolveSecond: (results: MarketSearchResult[]) => void = () => {};

		const firstPromise = new Promise<MarketSearchResult[]>((resolve) => {
			resolveFirst = resolve;
		});
		const secondPromise = new Promise<MarketSearchResult[]>((resolve) => {
			resolveSecond = resolve;
		});

		mockSearchSecurities.mockImplementation((query: string) => {
			if (query === 'AAPL') return firstPromise;
			if (query === 'MSFT') return secondPromise;
			return Promise.resolve([]);
		});

		render(WatchlistSecurityPicker, {
			props: { watchlistId: 'wl-1' }
		});

		const input = screen.getByPlaceholderText('Search securities to add...');

		// Launch query A (AAPL)
		await fireEvent.input(input, { target: { value: 'AAPL' } });
		await waitFor(() => expect(mockSearchSecurities).toHaveBeenCalledWith('AAPL'));

		// Launch query B (MSFT)
		await fireEvent.input(input, { target: { value: 'MSFT' } });
		await waitFor(() => expect(mockSearchSecurities).toHaveBeenCalledWith('MSFT'));

		// Resolve query B first (out of order)
		resolveSecond([
			{ code: 'MSFT', exchange: 'NASDAQ', name: 'Microsoft Corp.', security_type: 'Stock' }
		]);

		// Picker shows query B results
		expect(await screen.findByText(/Microsoft Corp\./)).toBeInTheDocument();

		// Resolve query A second (stale)
		resolveFirst([
			{ code: 'AAPL', exchange: 'NASDAQ', name: 'Apple Inc.', security_type: 'Stock' }
		]);

		// Wait briefly and verify query A results were dropped and query B results remain
		await new Promise((r) => setTimeout(r, 50));
		expect(screen.getByText(/Microsoft Corp\./)).toBeInTheDocument();
		expect(screen.queryByText(/Apple Inc\./)).not.toBeInTheDocument();
	});

	it('ignores errors from stale out-of-order queries', async () => {
		let rejectFirst: (err: Error) => void = () => {};
		let resolveSecond: (results: MarketSearchResult[]) => void = () => {};

		const firstPromise = new Promise<MarketSearchResult[]>((_, reject) => {
			rejectFirst = reject;
		});
		const secondPromise = new Promise<MarketSearchResult[]>((resolve) => {
			resolveSecond = resolve;
		});

		mockSearchSecurities.mockImplementation((query: string) => {
			if (query === 'FAIL') return firstPromise;
			if (query === 'NVDA') return secondPromise;
			return Promise.resolve([]);
		});

		render(WatchlistSecurityPicker, {
			props: { watchlistId: 'wl-1' }
		});

		const input = screen.getByPlaceholderText('Search securities to add...');

		await fireEvent.input(input, { target: { value: 'FAIL' } });
		await waitFor(() => expect(mockSearchSecurities).toHaveBeenCalledWith('FAIL'));

		await fireEvent.input(input, { target: { value: 'NVDA' } });
		await waitFor(() => expect(mockSearchSecurities).toHaveBeenCalledWith('NVDA'));

		// Resolve second query
		resolveSecond([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'Nvidia Corp.', security_type: 'Stock' }
		]);
		expect(await screen.findByText(/Nvidia Corp\./)).toBeInTheDocument();

		// Stale first query rejects
		rejectFirst(new Error('Network failure'));
		await new Promise((r) => setTimeout(r, 50));

		// Stale error is ignored; valid result remains
		expect(screen.queryByRole('alert')).not.toBeInTheDocument();
		expect(screen.getByText(/Nvidia Corp\./)).toBeInTheDocument();
	});

	it('clears results and ignores pending requests when query length is less than 2', async () => {
		let resolvePending: (results: MarketSearchResult[]) => void = () => {};
		const pendingPromise = new Promise<MarketSearchResult[]>((resolve) => {
			resolvePending = resolve;
		});

		mockSearchSecurities.mockReturnValue(pendingPromise);

		render(WatchlistSecurityPicker, {
			props: { watchlistId: 'wl-1' }
		});

		const input = screen.getByPlaceholderText('Search securities to add...');
		await fireEvent.input(input, { target: { value: 'GOOG' } });
		await waitFor(() => expect(mockSearchSecurities).toHaveBeenCalledWith('GOOG'));

		// Query shortened to 1 char
		await fireEvent.input(input, { target: { value: 'G' } });

		// Wait for debounce to fire the trimmed.length < 2 branch
		await new Promise((r) => setTimeout(r, 350));

		// Resolve previous search
		resolvePending([
			{ code: 'GOOG', exchange: 'NASDAQ', name: 'Alphabet Inc.', security_type: 'Stock' }
		]);
		await new Promise((r) => setTimeout(r, 50));

		// Stale results should not show up
		expect(screen.queryByText(/Alphabet Inc\./)).not.toBeInTheDocument();
	});

	it('delegates selection to watchlistService.addSecurity', async () => {
		mockSearchSecurities.mockResolvedValue([
			{ code: 'TSLA', exchange: 'NASDAQ', name: 'Tesla Inc.', security_type: 'Stock' }
		]);

		render(WatchlistSecurityPicker, {
			props: { watchlistId: 'wl-1' }
		});

		const input = screen.getByPlaceholderText('Search securities to add...');
		await fireEvent.input(input, { target: { value: 'TSLA' } });

		const item = await screen.findByText(/Tesla Inc\./);
		await fireEvent.click(item);

		expect(mockAddSecurity).toHaveBeenCalledWith('wl-1', {
			code: 'TSLA',
			exchange: 'NASDAQ',
			name: 'Tesla Inc.',
			security_type: 'Stock'
		});
	});
});
