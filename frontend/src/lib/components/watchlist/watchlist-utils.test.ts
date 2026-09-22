import { describe, expect, it, vi } from 'vitest';
import type { WatchlistRead, WatchlistSecuritySchema } from '$lib/api/marketService';
import {
	formatDateAdded,
	formatPrice,
	formatPriceChangePercent,
	handleReorderKeydown,
	moveItem,
	normalizeWatchlistSort,
	sortSecurities,
	sortWatchlistsByOrder
} from './watchlist-utils';

function makeWatchlist(id: string, name: string): WatchlistRead {
	return {
		id,
		user_id: 'user-1',
		name,
		sort: 'custom',
		securities: []
	};
}

function makeSecurity(
	id: string,
	symbol: string,
	name: string,
	price?: number | null,
	changePercent?: number | null,
	position = 0,
	addedAt = '2024-01-01T00:00:00Z'
): WatchlistSecuritySchema {
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
		daily_price_change_percent: changePercent,
		added_at: addedAt,
		position
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

		it('sorts by custom (ascending position, oldest added first)', () => {
			const first = makeSecurity('1', 'TSLA', 'Tesla Inc', 250, 5.0, 0);
			const second = makeSecurity('2', 'AAPL', 'Apple Inc', 180, 2.5, 1);
			const third = makeSecurity('3', 'MSFT', 'Microsoft Corp', 400, -1.2, 2);

			const sorted = sortSecurities([third, first, second], 'custom');

			expect(sorted.map((s) => s.symbol)).toEqual(['TSLA', 'AAPL', 'MSFT']);
		});

		it('sorts by date_added (newest first)', () => {
			const oldest = makeSecurity('1', 'AAPL', 'Apple Inc', 180, 2.5, 0, '2024-01-01T00:00:00Z');
			const middle = makeSecurity(
				'2',
				'MSFT',
				'Microsoft Corp',
				400,
				-1.2,
				1,
				'2024-02-01T00:00:00Z'
			);
			const newest = makeSecurity('3', 'TSLA', 'Tesla Inc', 250, 5.0, 2, '2024-03-01T00:00:00Z');

			const sorted = sortSecurities([oldest, newest, middle], 'date_added');

			expect(sorted.map((s) => s.symbol)).toEqual(['TSLA', 'MSFT', 'AAPL']);
		});

		it('sorts by date_added_asc (oldest first)', () => {
			const oldest = makeSecurity('1', 'AAPL', 'Apple Inc', 180, 2.5, 2, '2024-01-01T00:00:00Z');
			const middle = makeSecurity(
				'2',
				'MSFT',
				'Microsoft Corp',
				400,
				-1.2,
				1,
				'2024-02-01T00:00:00Z'
			);
			const newest = makeSecurity('3', 'TSLA', 'Tesla Inc', 250, 5.0, 0, '2024-03-01T00:00:00Z');

			const sorted = sortSecurities([newest, oldest, middle], 'date_added_asc');

			expect(sorted.map((s) => s.symbol)).toEqual(['AAPL', 'MSFT', 'TSLA']);
		});

		it('falls back to custom (position) order when the key is absent or unrecognised', () => {
			// Positions deliberately disagree with array order to prove the fallback sorts.
			const first = makeSecurity('1', 'TSLA', 'Tesla Inc', 250, 5.0, 0);
			const second = makeSecurity('2', 'AAPL', 'Apple Inc', 180, 2.5, 1);
			const list = [second, first];

			expect(sortSecurities(list, null).map((s) => s.symbol)).toEqual(['TSLA', 'AAPL']);
			expect(sortSecurities(list, undefined).map((s) => s.symbol)).toEqual(['TSLA', 'AAPL']);
			expect(sortSecurities(list, 'unknown').map((s) => s.symbol)).toEqual(['TSLA', 'AAPL']);
			expect(sortSecurities(list, 'name_desc').map((s) => s.symbol)).toEqual(['TSLA', 'AAPL']);
		});

		it('does not mutate the input array', () => {
			const first = makeSecurity('1', 'TSLA', 'Tesla Inc', 250, 5.0, 0);
			const second = makeSecurity('2', 'AAPL', 'Apple Inc', 180, 2.5, 1);
			const list = [second, first];

			sortSecurities(list, 'custom');

			expect(list.map((s) => s.symbol)).toEqual(['AAPL', 'TSLA']);
		});
	});

	describe('normalizeWatchlistSort', () => {
		it('passes through every known key', () => {
			for (const key of [
				'custom',
				'name_asc',
				'price_change_desc',
				'price_change_asc',
				'date_added',
				'date_added_asc'
			] as const) {
				expect(normalizeWatchlistSort(key)).toBe(key);
			}
		});

		it('falls back to custom for absent or unrecognised keys', () => {
			expect(normalizeWatchlistSort(undefined)).toBe('custom');
			expect(normalizeWatchlistSort(null)).toBe('custom');
			expect(normalizeWatchlistSort('')).toBe('custom');
			expect(normalizeWatchlistSort('garbage')).toBe('custom');
		});
	});

	describe('moveItem', () => {
		it('moves an item forward to a later index', () => {
			expect(moveItem(['a', 'b', 'c', 'd'], 0, 2)).toEqual(['b', 'c', 'a', 'd']);
		});

		it('moves an item backward to an earlier index', () => {
			expect(moveItem(['a', 'b', 'c', 'd'], 3, 1)).toEqual(['a', 'd', 'b', 'c']);
		});

		it('is a no-op for equal indices', () => {
			expect(moveItem(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'b', 'c']);
		});

		it('is a no-op for out-of-range indices', () => {
			expect(moveItem(['a', 'b', 'c'], -1, 1)).toEqual(['a', 'b', 'c']);
			expect(moveItem(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
			expect(moveItem(['a', 'b', 'c'], 3, 1)).toEqual(['a', 'b', 'c']);
			expect(moveItem(['a', 'b', 'c'], 0, 3)).toEqual(['a', 'b', 'c']);
		});

		it('never mutates the input array and always returns a fresh copy', () => {
			const list = ['a', 'b', 'c'];
			const moved = moveItem(list, 0, 2);

			expect(list).toEqual(['a', 'b', 'c']);
			expect(moved).not.toBe(list);

			const noop = moveItem(list, 1, 1);
			expect(noop).not.toBe(list);
		});
	});

	describe('handleReorderKeydown', () => {
		function event(key: string) {
			return { key, preventDefault: vi.fn() };
		}

		it('moves one position up on ArrowUp and consumes the key', () => {
			const e = event('ArrowUp');
			const onMove = vi.fn();

			expect(handleReorderKeydown(e, 2, 3, onMove)).toBe(true);
			expect(e.preventDefault).toHaveBeenCalledTimes(1);
			expect(onMove).toHaveBeenCalledWith(2, 1);
		});

		it('moves one position down on ArrowDown and consumes the key', () => {
			const e = event('ArrowDown');
			const onMove = vi.fn();

			expect(handleReorderKeydown(e, 0, 3, onMove)).toBe(true);
			expect(e.preventDefault).toHaveBeenCalledTimes(1);
			expect(onMove).toHaveBeenCalledWith(0, 1);
		});

		it('consumes the key but does not move at the first and last position', () => {
			const up = event('ArrowUp');
			const upMove = vi.fn();
			expect(handleReorderKeydown(up, 0, 3, upMove)).toBe(true);
			expect(up.preventDefault).toHaveBeenCalledTimes(1);
			expect(upMove).not.toHaveBeenCalled();

			const down = event('ArrowDown');
			const downMove = vi.fn();
			expect(handleReorderKeydown(down, 2, 3, downMove)).toBe(true);
			expect(down.preventDefault).toHaveBeenCalledTimes(1);
			expect(downMove).not.toHaveBeenCalled();
		});

		it('leaves non-arrow keys untouched', () => {
			const e = event('Enter');
			const onMove = vi.fn();

			expect(handleReorderKeydown(e, 1, 3, onMove)).toBe(false);
			expect(e.preventDefault).not.toHaveBeenCalled();
			expect(onMove).not.toHaveBeenCalled();
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

	describe('formatDateAdded', () => {
		it('formats a valid ISO timestamp deterministically', () => {
			expect(formatDateAdded('2024-01-01T00:00:00Z')).toBe('Jan 1, 2024');
			expect(formatDateAdded('2024-03-15T12:30:00Z')).toBe('Mar 15, 2024');
		});

		it('returns null when the value is missing', () => {
			expect(formatDateAdded(null)).toBeNull();
			expect(formatDateAdded(undefined)).toBeNull();
			expect(formatDateAdded('')).toBeNull();
		});

		it('returns null for unparseable input', () => {
			expect(formatDateAdded('not-a-date')).toBeNull();
		});
	});
});
