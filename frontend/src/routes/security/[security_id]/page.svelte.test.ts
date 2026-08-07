import { describe, it, expect } from 'vitest';
import type { Candle } from '@/utils/finance/candle';
import type { UserPreferences } from '$lib/api/userPreferencesService';
import type { IndicatorConfig } from '$lib/api/indicatorsService';

// ---------------------------------------------------------------------------
// Helpers under test — imported directly from the real module the page uses
// ---------------------------------------------------------------------------
import {
	mergeChartPreferences,
	displayCandlesFor,
	shouldForceRefetch
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
