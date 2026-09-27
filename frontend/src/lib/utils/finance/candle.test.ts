import { describe, it, expect } from 'vitest';
import {
	calculateSplitRatio,
	applySplitAdjustment,
	mapPriceToCandle,
	transformToSplitAdjustedCandles,
	convertToHeikinAshi,
	type Candle
} from './candle';

describe('candle split adjustment', () => {
	it('calculates split ratio when adjusted_close differs from close', () => {
		// 2-for-1 split: close was 100, adjusted_close is 50
		expect(calculateSplitRatio(100, 50)).toBe(0.5);

		// 1-for-2 reverse split: close was 50, adjusted_close is 100
		expect(calculateSplitRatio(50, 100)).toBe(2);
	});

	it('returns null when adjusted_close is equal to close, missing, or invalid', () => {
		expect(calculateSplitRatio(100, 100)).toBeNull();
		expect(calculateSplitRatio(100, undefined)).toBeNull();
		expect(calculateSplitRatio(100, null)).toBeNull();
		expect(calculateSplitRatio(100, 0)).toBeNull();
		expect(calculateSplitRatio(0, 50)).toBeNull();
	});

	it('scales open, high, low, close according to split ratio', () => {
		const raw = {
			open: 100,
			high: 110,
			low: 95,
			close: 105,
			adjusted_close: 52.5 // ratio = 0.5
		};

		const adjusted = applySplitAdjustment(raw);
		expect(adjusted.open).toBe(50);
		expect(adjusted.high).toBe(55);
		expect(adjusted.low).toBe(47.5);
		expect(adjusted.close).toBe(52.5);
	});

	it('leaves OHLC unchanged when no split adjustment is needed', () => {
		const raw = {
			open: 100,
			high: 110,
			low: 95,
			close: 105,
			adjusted_close: 105
		};

		const adjusted = applySplitAdjustment(raw);
		expect(adjusted.open).toBe(100);
		expect(adjusted.high).toBe(110);
		expect(adjusted.low).toBe(95);
		expect(adjusted.close).toBe(105);
	});

	it('transforms an array of items to split-adjusted candles', () => {
		const items = [
			{
				time: '2024-01-01',
				open: 100,
				high: 120,
				low: 90,
				close: 100,
				adjusted_close: 50,
				volume: 1000
			},
			{
				time: '2024-01-02',
				open: 50,
				high: 55,
				low: 48,
				close: 52,
				adjusted_close: 52,
				volume: 1200
			}
		];

		const candles = transformToSplitAdjustedCandles(items);
		expect(candles[0]).toEqual({
			time: '2024-01-01',
			open: 50,
			high: 60,
			low: 45,
			close: 50,
			volume: 1000
		});
		expect(candles[1]).toEqual({
			time: '2024-01-02',
			open: 50,
			high: 55,
			low: 48,
			close: 52,
			volume: 1200
		});
	});

	it('computes continuous Heikin Ashi from split-adjusted candles', () => {
		const splitAdjusted: Candle[] = [
			{ time: '2024-01-01', open: 50, high: 60, low: 45, close: 50 },
			{ time: '2024-01-02', open: 50, high: 55, low: 48, close: 52 }
		];

		const ha = convertToHeikinAshi(splitAdjusted);
		expect(ha).toHaveLength(2);
		expect(ha[0].open).toBe((50 + 50) / 2);
		expect(ha[0].close).toBe((50 + 60 + 45 + 50) / 4);
		expect(ha[1].open).toBe((ha[0].open + ha[0].close) / 2);
	});

	describe('mapPriceToCandle', () => {
		it('maps daily price with date string and adjusts for split', () => {
			const price = {
				date: '2024-05-01',
				open: 200,
				high: 210,
				low: 190,
				close: 200,
				adjusted_close: 100, // 2-for-1 split (0.5x)
				volume: 50000
			};
			const candle = mapPriceToCandle(price, false);
			expect(candle).toEqual({
				time: '2024-05-01',
				open: 100,
				high: 105,
				low: 95,
				close: 100,
				volume: 50000
			});
		});

		it('maps intraday price with timestamp without split adjustment', () => {
			const price = {
				timestamp: '2024-05-01T14:30:00Z',
				open: 150,
				high: 155,
				low: 148,
				close: 152,
				volume: 10000
			};
			const candle = mapPriceToCandle(price, true);
			expect(candle.time).toBe(Math.floor(new Date('2024-05-01T14:30:00Z').getTime() / 1000));
			expect(candle.open).toBe(150);
			expect(candle.high).toBe(155);
			expect(candle.low).toBe(148);
			expect(candle.close).toBe(152);
			expect(candle.volume).toBe(10000);
		});

		it('handles missing adjusted_close cleanly without modifying OHLC', () => {
			const price = {
				date: '2024-05-01',
				open: '120.5',
				high: '125.0',
				low: '119.0',
				close: '122.0',
				volume: '2000'
			};
			const candle = mapPriceToCandle(price);
			expect(candle.open).toBe(120.5);
			expect(candle.high).toBe(125.0);
			expect(candle.low).toBe(119.0);
			expect(candle.close).toBe(122.0);
			expect(candle.volume).toBe(2000);
		});
	});
});
