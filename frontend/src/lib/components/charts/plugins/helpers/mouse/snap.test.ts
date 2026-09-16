import { describe, it, expect } from 'vitest';
import { findNearestLevel, snapPriceToWick } from './snap';
import type { Candle } from '$lib/utils/finance/candle';

describe('snap helpers', () => {
	describe('findNearestLevel', () => {
		it('returns the closest level price', () => {
			expect(findNearestLevel(105, [100, 110, 150])).toBe(100);
			expect(findNearestLevel(108, [100, 110, 150])).toBe(110);
		});

		it('resolves an exact midpoint tie to the earliest candidate', () => {
			expect(findNearestLevel(105, [110, 100])).toBe(110);
		});

		it('returns null for an empty list or non-finite price', () => {
			expect(findNearestLevel(100, [])).toBeNull();
			expect(findNearestLevel(NaN, [100, 110])).toBeNull();
			expect(findNearestLevel(Infinity, [100, 110])).toBeNull();
		});

		it('ignores non-finite level candidates', () => {
			expect(findNearestLevel(100, [NaN, Infinity, 120])).toBe(120);
			expect(findNearestLevel(100, [NaN, Infinity])).toBeNull();
		});
	});

	describe('snapPriceToWick', () => {
		const candle: Candle = {
			time: '2024-01-01',
			open: 100,
			high: 110,
			low: 90,
			close: 105
		};

		it('snaps to the nearest wick and ties to high', () => {
			expect(snapPriceToWick(106, candle)).toBe(110);
			expect(snapPriceToWick(94, candle)).toBe(90);
			expect(snapPriceToWick(100, candle)).toBe(110);
		});
	});
});
