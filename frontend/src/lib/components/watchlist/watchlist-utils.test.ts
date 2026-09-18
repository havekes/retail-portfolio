import { describe, expect, it } from 'vitest';
import type { SecuritySchema, WatchlistRead } from '$lib/api/marketService';
import {
	formatPrice,
	formatPriceChangePercent,
	sortSecurities,
	sortWatchlistsByOrder
} from './watchlist-utils';

function makeWatchlist(id: string, name: string): WatchlistRead {
	return {
		id,
		user_id: 'user-1',
		name,
		securities: []
	};
}

function makeSecurity(
	id: string,
	symbol: string,
	name: string,
	price?: number | null,
	changePercent?: number | null
): SecuritySchema {
	return {
		id,
		symbol,
		exchange: 'US',
		currency: 'USD',
		name,
		isin: null,
		is_active: true,
		updated_at: '2024-01-01T00:00:00Z',
		current_price: price,
		daily_price_change: null,
		daily_price_change_percent: changePercent
	};
}

describe('watchlist-utils', () => {
	describe('sortWatchlistsByOrder', () => {
		it('sorts watchlists matching the order array', () => {
			const w1 = makeWatchlist('1', 'One');
			const w2 = makeWatchlist('2', 'Two');
			const w3 = makeWatchlist('3', 'Three');

			const sorted = sortWatchlistsByOrder([w1, w2, w3], ['3', '1', '2']);
			expect(sorted.map((w) => w.id)).toEqual(['3', '1', '2']);
		});

		it('appends unlisted watchlists at the end', () => {
			const w1 = makeWatchlist('1', 'One');
			const w2 = makeWatchlist('2', 'Two');
			const w3 = makeWatchlist('3', 'Three');
			const w4 = makeWatchlist('4', 'Four');

			const sorted = sortWatchlistsByOrder([w1, w2, w3, w4], ['3', '1']);
			expect(sorted.map((w) => w.id)).toEqual(['3', '1', '2', '4']);
		});

		it('ignores non-existent IDs in order', () => {
			const w1 = makeWatchlist('1', 'One');
			const w2 = makeWatchlist('2', 'Two');

			const sorted = sortWatchlistsByOrder([w1, w2], ['999', '2', '888', '1']);
			expect(sorted.map((w) => w.id)).toEqual(['2', '1']);
		});

		it('returns a copy of watchlists if order is missing or empty', () => {
			const w1 = makeWatchlist('1', 'One');
			const w2 = makeWatchlist('2', 'Two');

			expect(sortWatchlistsByOrder([w1, w2], null).map((w) => w.id)).toEqual(['1', '2']);
			expect(sortWatchlistsByOrder([w1, w2], []).map((w) => w.id)).toEqual(['1', '2']);
		});
	});

	describe('sortSecurities', () => {
		const sA = makeSecurity('1', 'AAPL', 'Apple Inc', 180, 2.5);
		const sM = makeSecurity('2', 'MSFT', 'Microsoft Corp', 400, -1.2);
		const sT = makeSecurity('3', 'TSLA', 'Tesla Inc', 250, 5.0);
		const sN = makeSecurity('4', 'NVDA', 'Nvidia Corp', 120, null);

		it('sorts by name_asc', () => {
			const sorted = sortSecurities([sT, sA, sM], 'name_asc');
			expect(sorted.map((s) => s.symbol)).toEqual(['AAPL', 'MSFT', 'TSLA']);
			expect(sorted.map((s) => s.name)).toEqual(['Apple Inc', 'Microsoft Corp', 'Tesla Inc']);
		});

		it('sorts by name_desc', () => {
			const sorted = sortSecurities([sA, sT, sM], 'name_desc');
			expect(sorted.map((s) => s.name)).toEqual(['Tesla Inc', 'Microsoft Corp', 'Apple Inc']);
		});

		it('sorts by price_change_desc (gainers first, nulls last)', () => {
			const sorted = sortSecurities([sM, sN, sT, sA], 'price_change_desc');
			expect(sorted.map((s) => s.symbol)).toEqual(['TSLA', 'AAPL', 'MSFT', 'NVDA']);
		});

		it('sorts by price_change_asc (losers first, nulls last)', () => {
			const sorted = sortSecurities([sA, sN, sM, sT], 'price_change_asc');
			expect(sorted.map((s) => s.symbol)).toEqual(['MSFT', 'AAPL', 'TSLA', 'NVDA']);
		});

		it('returns original list copy when sortKey is empty or unrecognized', () => {
			const list = [sA, sM, sT];
			expect(sortSecurities(list, null)).toEqual(list);
			expect(sortSecurities(list, 'unknown')).toEqual(list);
		});
	});

	describe('formatPrice', () => {
		it('formats numeric prices with 2 decimal places', () => {
			expect(formatPrice(50.25)).toBe('50.25');
			expect(formatPrice(100)).toBe('100.00');
			expect(formatPrice(0)).toBe('0.00');
		});

		it('handles string prices correctly', () => {
			expect(formatPrice('42.1')).toBe('42.10');
		});

		it('returns "-" when price is absent or invalid', () => {
			expect(formatPrice(null)).toBe('-');
			expect(formatPrice(undefined)).toBe('-');
			expect(formatPrice('')).toBe('-');
			expect(formatPrice(NaN)).toBe('-');
		});
	});

	describe('formatPriceChangePercent', () => {
		it('formats positive change with "+" prefix', () => {
			expect(formatPriceChangePercent(1.65)).toBe('+1.65%');
			expect(formatPriceChangePercent(0.01)).toBe('+0.01%');
		});

		it('formats negative change with "-" prefix', () => {
			expect(formatPriceChangePercent(-0.82)).toBe('-0.82%');
		});

		it('formats zero without sign', () => {
			expect(formatPriceChangePercent(0)).toBe('0.00%');
			expect(formatPriceChangePercent(-0.00001)).toBe('0.00%');
		});

		it('returns "-" when absent or invalid', () => {
			expect(formatPriceChangePercent(null)).toBe('-');
			expect(formatPriceChangePercent(undefined)).toBe('-');
			expect(formatPriceChangePercent('')).toBe('-');
			expect(formatPriceChangePercent(NaN)).toBe('-');
		});
	});
});
