import { describe, it, expect } from 'vitest';
import type { Candle } from './candle';
import {
	parseCandleTimeToDate,
	getPeriodCutoffDate,
	getBenchmarkPrice,
	calculateHoldingGain,
	filterCandlesForPeriod
} from './holdings-metrics';

describe('holdings-metrics', () => {
	const refDate = new Date(2024, 5, 15, 12, 0, 0); // June 15, 2024 12:00:00

	const sampleCandles: Candle[] = [
		{ time: '2023-01-02', open: 90, high: 95, low: 88, close: 92 },
		{ time: '2023-12-29', open: 100, high: 102, low: 99, close: 101 },
		{ time: '2024-01-02', open: 102, high: 105, low: 101, close: 103 },
		{ time: '2024-05-15', open: 110, high: 112, low: 109, close: 111 },
		{ time: '2024-06-08', open: 115, high: 118, low: 114, close: 116 },
		{ time: '2024-06-14', open: 120, high: 122, low: 119, close: 121 },
		{ time: '2024-06-15', open: 121, high: 125, low: 120, close: 124 }
	];

	describe('parseCandleTimeToDate', () => {
		it('parses unix timestamp in seconds', () => {
			const date = parseCandleTimeToDate(1718452800);
			expect(date.getTime()).toBe(1718452800 * 1000);
		});

		it('parses YYYY-MM-DD string into local date', () => {
			const date = parseCandleTimeToDate('2024-06-15');
			expect(date.getFullYear()).toBe(2024);
			expect(date.getMonth()).toBe(5); // June
			expect(date.getDate()).toBe(15);
		});

		it('parses ISO datetime string', () => {
			const date = parseCandleTimeToDate('2024-06-15T14:30:00Z');
			expect(date.toISOString()).toBe('2024-06-15T14:30:00.000Z');
		});

		it('parses BusinessDay object', () => {
			const date = parseCandleTimeToDate({ year: 2024, month: 6, day: 15 });
			expect(date.getUTCFullYear()).toBe(2024);
			expect(date.getUTCMonth()).toBe(5);
			expect(date.getUTCDate()).toBe(15);
		});
	});

	describe('getPeriodCutoffDate', () => {
		it('calculates 1D cutoff as 1 day prior', () => {
			const cutoff = getPeriodCutoffDate('1D', refDate);
			expect(cutoff).not.toBeNull();
			expect(cutoff?.getDate()).toBe(14);
			expect(cutoff?.getMonth()).toBe(5);
			expect(cutoff?.getFullYear()).toBe(2024);
		});

		it('calculates 1W cutoff as 7 days prior', () => {
			const cutoff = getPeriodCutoffDate('1W', refDate);
			expect(cutoff).not.toBeNull();
			expect(cutoff?.getDate()).toBe(8);
			expect(cutoff?.getMonth()).toBe(5);
			expect(cutoff?.getFullYear()).toBe(2024);
		});

		it('calculates 1M cutoff as 1 month prior', () => {
			const cutoff = getPeriodCutoffDate('1M', refDate);
			expect(cutoff).not.toBeNull();
			expect(cutoff?.getDate()).toBe(15);
			expect(cutoff?.getMonth()).toBe(4); // May
			expect(cutoff?.getFullYear()).toBe(2024);
		});

		it('calculates 1Y cutoff as 1 year prior', () => {
			const cutoff = getPeriodCutoffDate('1Y', refDate);
			expect(cutoff).not.toBeNull();
			expect(cutoff?.getDate()).toBe(15);
			expect(cutoff?.getMonth()).toBe(5);
			expect(cutoff?.getFullYear()).toBe(2023);
		});

		it('calculates YTD cutoff as start of current year', () => {
			const cutoff = getPeriodCutoffDate('YTD', refDate);
			expect(cutoff).not.toBeNull();
			expect(cutoff?.getFullYear()).toBe(2024);
			expect(cutoff?.getMonth()).toBe(0); // Jan
			expect(cutoff?.getDate()).toBe(1);
		});

		it('returns null for ALL', () => {
			expect(getPeriodCutoffDate('ALL', refDate)).toBeNull();
		});

		it('returns null for invalid/unknown period', () => {
			// @ts-expect-error test invalid period input
			expect(getPeriodCutoffDate('INVALID', refDate)).toBeNull();
		});

		it('defaults referenceDate to current date when omitted', () => {
			const cutoff = getPeriodCutoffDate('1D');
			expect(cutoff).toBeInstanceOf(Date);
		});
	});

	describe('getBenchmarkPrice', () => {
		describe('ALL period', () => {
			it('returns averageCost when provided', () => {
				expect(getBenchmarkPrice(sampleCandles, 'ALL', 105.5)).toBe(105.5);
			});

			it('returns 0 when averageCost is 0', () => {
				expect(getBenchmarkPrice(sampleCandles, 'ALL', 0)).toBe(0);
			});

			it('returns null when averageCost is undefined or null or NaN', () => {
				expect(getBenchmarkPrice(sampleCandles, 'ALL', undefined)).toBeNull();
				expect(getBenchmarkPrice(sampleCandles, 'ALL', null)).toBeNull();
				expect(getBenchmarkPrice(sampleCandles, 'ALL', NaN)).toBeNull();
			});
		});

		describe('Timeframe periods (1D, 1W, 1M, 1Y, YTD)', () => {
			it('returns null for empty candle array', () => {
				expect(getBenchmarkPrice([], '1D', 100, refDate)).toBeNull();
				expect(getBenchmarkPrice([], '1W', 100, refDate)).toBeNull();
				expect(getBenchmarkPrice([], '1M', 100, refDate)).toBeNull();
				expect(getBenchmarkPrice([], '1Y', 100, refDate)).toBeNull();
				expect(getBenchmarkPrice([], 'YTD', 100, refDate)).toBeNull();
			});

			it('returns the single candle close when only 1 candle exists', () => {
				const single: Candle[] = [
					{ time: '2024-06-15', open: 120, high: 125, low: 120, close: 124 }
				];
				expect(getBenchmarkPrice(single, '1D', undefined, refDate)).toBe(124);
			});

			it('resolves 1D benchmark candle (previous day close)', () => {
				// refDate is 2024-06-15, cutoff is 2024-06-14
				// Candle on 2024-06-14 has close 121
				expect(getBenchmarkPrice(sampleCandles, '1D', undefined, refDate)).toBe(121);
			});

			it('resolves 1D benchmark across weekend gap', () => {
				// Monday June 17, 2024. Cutoff is Sunday June 16.
				// Latest candle <= June 16 is Friday June 14 (or Saturday June 15 if present)
				const mondayRef = new Date(2024, 5, 17);
				const weekendCandles: Candle[] = [
					{ time: '2024-06-14', open: 120, high: 122, low: 119, close: 121 }, // Friday
					{ time: '2024-06-17', open: 122, high: 126, low: 121, close: 125 } // Monday
				];
				// 1D cutoff from Monday is Sunday June 16; closest candle <= Sunday is Friday
				expect(getBenchmarkPrice(weekendCandles, '1D', undefined, mondayRef)).toBe(121);
			});

			it('resolves 1W benchmark candle (7 days prior)', () => {
				// Cutoff is 2024-06-08 -> Candle on 2024-06-08 has close 116
				expect(getBenchmarkPrice(sampleCandles, '1W', undefined, refDate)).toBe(116);
			});

			it('resolves 1M benchmark candle (1 month prior)', () => {
				// Cutoff is 2024-05-15 -> Candle on 2024-05-15 has close 111
				expect(getBenchmarkPrice(sampleCandles, '1M', undefined, refDate)).toBe(111);
			});

			it('resolves 1Y benchmark candle (1 year prior)', () => {
				// Cutoff is 2023-06-15 -> closest prior candle is 2023-01-02 (close 92)
				expect(getBenchmarkPrice(sampleCandles, '1Y', undefined, refDate)).toBe(92);
			});

			it('resolves YTD benchmark candle (start of year)', () => {
				// Cutoff is 2024-01-01 -> closest prior candle is 2023-12-29 (close 101)
				expect(getBenchmarkPrice(sampleCandles, 'YTD', undefined, refDate)).toBe(101);
			});

			it('falls back to earliest available candle if all candles are after cutoff', () => {
				const recentOnlyCandles: Candle[] = [
					{ time: '2024-06-10', open: 118, high: 120, low: 117, close: 119 },
					{ time: '2024-06-15', open: 121, high: 125, low: 120, close: 124 }
				];
				// 1Y cutoff is 2023-06-15; no candle <= 2023-06-15, returns earliest (119)
				expect(getBenchmarkPrice(recentOnlyCandles, '1Y', undefined, refDate)).toBe(119);
			});

			it('handles unsorted candles array correctly', () => {
				const unsortedCandles = [...sampleCandles].reverse();
				expect(getBenchmarkPrice(unsortedCandles, '1D', undefined, refDate)).toBe(121);
				expect(getBenchmarkPrice(unsortedCandles, '1W', undefined, refDate)).toBe(116);
			});
		});
	});

	describe('calculateHoldingGain', () => {
		it('calculates positive gain correctly', () => {
			const result = calculateHoldingGain(120, 100, 10);
			expect(result.gainAmount).toBe(200); // (120 - 100) * 10
			expect(result.gainPercent).toBe(20); // (20 / 100) * 100
		});

		it('calculates negative loss correctly', () => {
			const result = calculateHoldingGain(80, 100, 5);
			expect(result.gainAmount).toBe(-100); // (80 - 100) * 5
			expect(result.gainPercent).toBe(-20); // (-20 / 100) * 100
		});

		it('calculates zero gain for flat price', () => {
			const result = calculateHoldingGain(100, 100, 15);
			expect(result.gainAmount).toBe(0);
			expect(result.gainPercent).toBe(0);
		});

		it('handles fractional quantities', () => {
			const result = calculateHoldingGain(150, 100, 0.5);
			expect(result.gainAmount).toBe(25); // (150 - 100) * 0.5
			expect(result.gainPercent).toBe(50);
		});

		it('handles zero benchmark price gracefully without division by zero', () => {
			const result = calculateHoldingGain(100, 0, 10);
			expect(result.gainAmount).toBe(1000);
			expect(result.gainPercent).toBe(0);
		});

		it('returns 0 values for invalid/NaN inputs', () => {
			expect(calculateHoldingGain(NaN, 100, 10)).toEqual({ gainAmount: 0, gainPercent: 0 });
			expect(calculateHoldingGain(100, NaN, 10)).toEqual({ gainAmount: 0, gainPercent: 0 });
			expect(calculateHoldingGain(100, 100, NaN)).toEqual({ gainAmount: 0, gainPercent: 0 });
		});
	});

	describe('filterCandlesForPeriod', () => {
		it('returns empty array when candles is empty', () => {
			expect(filterCandlesForPeriod([], '1D', refDate)).toEqual([]);
			expect(filterCandlesForPeriod([], 'ALL', refDate)).toEqual([]);
		});

		it('returns all candles for ALL period', () => {
			const result = filterCandlesForPeriod(sampleCandles, 'ALL', refDate);
			expect(result).toHaveLength(sampleCandles.length);
			expect(result).toEqual(sampleCandles);
		});

		it('filters candles for 1D window', () => {
			// Cutoff is 2024-06-14 -> candles on 2024-06-14 and 2024-06-15
			const result = filterCandlesForPeriod(sampleCandles, '1D', refDate);
			expect(result).toHaveLength(2);
			expect(result.map((c) => c.time)).toEqual(['2024-06-14', '2024-06-15']);
		});

		it('filters candles for 1W window', () => {
			// Cutoff is 2024-06-08 -> candles on 2024-06-08, 2024-06-14, 2024-06-15
			const result = filterCandlesForPeriod(sampleCandles, '1W', refDate);
			expect(result).toHaveLength(3);
			expect(result.map((c) => c.time)).toEqual(['2024-06-08', '2024-06-14', '2024-06-15']);
		});

		it('filters candles for YTD window', () => {
			// Cutoff is 2024-01-01 -> all 2024 candles (5 candles)
			const result = filterCandlesForPeriod(sampleCandles, 'YTD', refDate);
			expect(result).toHaveLength(5);
			expect(result.every((c) => String(c.time).startsWith('2024'))).toBe(true);
		});

		it('returns empty array if no candles meet cutoff', () => {
			const oldCandles: Candle[] = [{ time: '2020-01-01', open: 50, high: 55, low: 49, close: 52 }];
			expect(filterCandlesForPeriod(oldCandles, '1D', refDate)).toEqual([]);
		});
	});
});
