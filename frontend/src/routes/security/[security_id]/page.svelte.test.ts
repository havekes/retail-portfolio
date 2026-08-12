import { describe, it, expect } from 'vitest';
import type { Candle } from '@/utils/finance/candle';
import type { Time } from 'lightweight-charts';
import type { UserPreferences } from '$lib/api/userPreferencesService';
import type { IndicatorConfig } from '$lib/api/indicatorsService';

// ---------------------------------------------------------------------------
// Helpers under test — imported directly from the real module the page uses
// ---------------------------------------------------------------------------
import {
	mergeChartPreferences,
	displayCandlesFor,
	shouldForceRefetch,
	parseCandleTime,
	mergeCandles,
	shouldFetchMoreData
} from '$lib/chart-preferences';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------
const mockRawCandle: Candle = {
	time: '2024-01-01',
	open: 100,
	high: 110,
	low: 95,
	close: 105,
	volume: 1000
};

const mockHaCandle: Candle = {
	time: '2024-01-01',
	open: 101,
	high: 111,
	low: 96,
	close: 106,
	volume: 1000
};

const indicatorPrefs: Record<string, IndicatorConfig> = {
	sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
};

const prefsWithIndicators: UserPreferences = {
	indicators: indicatorPrefs
};

const emptyPrefs: UserPreferences = {};

// ---------------------------------------------------------------------------
// mergeChartPreferences — the read-merge-write contract
// ---------------------------------------------------------------------------
describe('mergeChartPreferences', () => {
	it('merges partial into prefs and preserves indicators', () => {
		const result = mergeChartPreferences(prefsWithIndicators, { timeframe: '4h' });
		expect(result.timeframe).toBe('4h');
		expect(result.indicators).toEqual(indicatorPrefs);
	});

	it('merges partial into prefs and preserves chart_style', () => {
		const prefs: UserPreferences = {
			chart_style: 'heikin_ashi',
			indicators: indicatorPrefs
		};
		const result = mergeChartPreferences(prefs, { timeframe: '1h' });
		expect(result.chart_style).toBe('heikin_ashi');
		expect(result.timeframe).toBe('1h');
		expect(result.indicators).toEqual(indicatorPrefs);
	});

	it('fills in indicators as {} when prefs has none', () => {
		const result = mergeChartPreferences(emptyPrefs, { chart_style: 'candlestick' });
		expect(result.chart_style).toBe('candlestick');
		expect(result.indicators).toEqual({});
	});

	it('partial keys overwrite existing keys', () => {
		const prefs: UserPreferences = {
			timeframe: '1d',
			chart_style: 'heikin_ashi',
			indicators: indicatorPrefs
		};
		const result = mergeChartPreferences(prefs, { timeframe: '1h', chart_style: 'candlestick' });
		expect(result.timeframe).toBe('1h');
		expect(result.chart_style).toBe('candlestick');
		expect(result.indicators).toEqual(indicatorPrefs);
	});

	it('partial does not clobber indicators when partial has no indicator key', () => {
		const result = mergeChartPreferences(prefsWithIndicators, { timeframe: '1m' });
		expect(result.indicators).toEqual(indicatorPrefs);
		expect(result.timeframe).toBe('1m');
	});

	it('partial can clobber indicators when it provides its own', () => {
		const newIndicators: Record<string, IndicatorConfig> = {
			rsi: { enabled: true, color: '#06b6d4', settings: { period: 14 } }
		};
		const result = mergeChartPreferences(prefsWithIndicators, {
			timeframe: '4h',
			indicators: newIndicators
		});
		expect(result.indicators).toEqual(newIndicators);
		expect(result.timeframe).toBe('4h');
	});
});

// ---------------------------------------------------------------------------
// displayCandlesFor — which candles the chart receives
// ---------------------------------------------------------------------------
describe('displayCandlesFor', () => {
	it('returns HA candles for heikin_ashi style', () => {
		const rawArr = [mockRawCandle];
		const haArr = [mockHaCandle];
		const result = displayCandlesFor('heikin_ashi', rawArr, haArr);
		expect(result).toBe(haArr); // same reference
		expect(result[0].open).toBe(101); // HA open, not raw
	});

	it('returns raw candles for candlestick style', () => {
		const rawArr = [mockRawCandle];
		const haArr = [mockHaCandle];
		const result = displayCandlesFor('candlestick', rawArr, haArr);
		expect(result).toBe(rawArr); // same reference
		expect(result[0].open).toBe(100); // raw open, not HA
	});

	it('raw and HA results are different references', () => {
		const raw = [mockRawCandle];
		const ha = [mockHaCandle];
		const haResult = displayCandlesFor('heikin_ashi', raw, ha);
		const rawResult = displayCandlesFor('candlestick', raw, ha);
		expect(haResult).not.toBe(rawResult);
	});
});

// ---------------------------------------------------------------------------
// shouldForceRefetch — force-flag decision logic
// ---------------------------------------------------------------------------
describe('shouldForceRefetch', () => {
	it('forces refetch when force is true even if interval matches', () => {
		expect(shouldForceRefetch('1d', '1d', true)).toBe(true);
	});

	it('does not force refetch when force is false and interval matches', () => {
		expect(shouldForceRefetch('1d', '1d', false)).toBe(false);
	});

	it('forces refetch when intervals differ regardless of force flag', () => {
		expect(shouldForceRefetch('1d', '1h', false)).toBe(true);
		expect(shouldForceRefetch('1d', '1h', true)).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// parseCandleTime — convert Lightweight Charts Time to Date
// ---------------------------------------------------------------------------
describe('parseCandleTime', () => {
	it('converts Unix timestamp in seconds to Date', () => {
		const date = parseCandleTime(1700000000 as unknown as Time);
		expect(date.getTime()).toBe(1700000000 * 1000);
	});

	it('converts YYYY-MM-DD string to Date', () => {
		const date = parseCandleTime('2024-01-15');
		expect(date.getFullYear()).toBe(2024);
		expect(date.getMonth()).toBe(0);
		expect(date.getDate()).toBe(15);
	});

	it('converts BusinessDay object to Date', () => {
		const date = parseCandleTime({ year: 2024, month: 2, day: 20 });
		expect(date.getFullYear()).toBe(2024);
		expect(date.getMonth()).toBe(1);
		expect(date.getDate()).toBe(20);
	});
});

// ---------------------------------------------------------------------------
// mergeCandles — prepending & deduplicating historical price chunks
// ---------------------------------------------------------------------------
describe('mergeCandles', () => {
	it('prepends new older candles to existing candles', () => {
		const existing: Candle[] = [
			{ time: '2024-01-03', open: 10, high: 11, low: 9, close: 10 },
			{ time: '2024-01-04', open: 10, high: 12, low: 10, close: 11 }
		];
		const incoming: Candle[] = [
			{ time: '2024-01-01', open: 8, high: 9, low: 7, close: 8 },
			{ time: '2024-01-02', open: 9, high: 10, low: 8, close: 9 }
		];

		const { merged, addedCount } = mergeCandles(existing, incoming);
		expect(addedCount).toBe(2);
		expect(merged.length).toBe(4);
		expect(merged[0].time).toBe('2024-01-01');
		expect(merged[1].time).toBe('2024-01-02');
		expect(merged[2].time).toBe('2024-01-03');
		expect(merged[3].time).toBe('2024-01-04');
	});

	it('deduplicates candles with overlapping dates', () => {
		const existing: Candle[] = [
			{ time: '2024-01-02', open: 9, high: 10, low: 8, close: 9 },
			{ time: '2024-01-03', open: 10, high: 11, low: 9, close: 10 }
		];
		const incoming: Candle[] = [
			{ time: '2024-01-01', open: 8, high: 9, low: 7, close: 8 },
			{ time: '2024-01-02', open: 9, high: 10, low: 8, close: 9 } // duplicate
		];

		const { merged, addedCount } = mergeCandles(existing, incoming);
		expect(addedCount).toBe(1);
		expect(merged.length).toBe(3);
		expect(merged[0].time).toBe('2024-01-01');
	});

	it('returns addedCount = 0 when all incoming candles are duplicates or empty', () => {
		const existing: Candle[] = [{ time: '2024-01-01', open: 8, high: 9, low: 7, close: 8 }];

		const resEmpty = mergeCandles(existing, []);
		expect(resEmpty.addedCount).toBe(0);
		expect(resEmpty.merged).toEqual(existing);

		const resDuplicates = mergeCandles(existing, existing);
		expect(resDuplicates.addedCount).toBe(0);
		expect(resDuplicates.merged).toEqual(existing);
	});
});

// ---------------------------------------------------------------------------
// shouldFetchMoreData — pagination gate logic
// ---------------------------------------------------------------------------
describe('shouldFetchMoreData', () => {
	it('allows fetching when not loading, hasMoreData is true, securityId and candles exist', () => {
		expect(shouldFetchMoreData(false, true, 'sec-123', 50)).toBe(true);
	});

	it('prevents fetching when isLoadingMore is true', () => {
		expect(shouldFetchMoreData(true, true, 'sec-123', 50)).toBe(false);
	});

	it('prevents fetching when hasMoreData is false', () => {
		expect(shouldFetchMoreData(false, false, 'sec-123', 50)).toBe(false);
	});

	it('prevents fetching when securityId is missing or candles count is 0', () => {
		expect(shouldFetchMoreData(false, true, undefined, 50)).toBe(false);
		expect(shouldFetchMoreData(false, true, 'sec-123', 0)).toBe(false);
	});
});
