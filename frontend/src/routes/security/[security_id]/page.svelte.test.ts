import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import type { Component } from 'svelte';
import type { Candle } from '@/utils/finance/candle';
import type { Time } from 'lightweight-charts';
import type { UserPreferences } from '$lib/api/userPreferencesService';
import type { IndicatorConfig } from '$lib/api/indicatorsService';
import type { DegreeWaveCount, SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import { updateSecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import type {
	FibRetracementDrawing,
	FibExtensionDrawing,
	SecurityFibonacciTools
} from '$lib/utils/finance/fibonacci';
import { updateSecurityFibonacciTools } from '$lib/utils/finance/fibonacci';
if (typeof globalThis.Path2D === 'undefined') {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	(globalThis as any).Path2D = class Path2D {
		addPath() {}
	};
}

if (typeof globalThis.ResizeObserver === 'undefined') {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	(globalThis as any).ResizeObserver = class ResizeObserver {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

const mockGetPrices = vi.fn().mockResolvedValue({ items: [] });

vi.mock('$lib/api/marketService', () => ({
	getMarketService: () => ({
		getPrices: mockGetPrices
	})
}));

vi.mock('$lib/api/userPreferencesService', () => {
	const mockGetPreferences = vi.fn().mockResolvedValue({});
	const mockPatchPreferences = vi.fn().mockResolvedValue({});
	const mockSavePreferences = vi.fn().mockResolvedValue({});
	return {
		userPreferencesService: {
			getPreferences: mockGetPreferences,
			patchPreferences: mockPatchPreferences,
			savePreferences: mockSavePreferences
		},
		getUserPreferencesService: () => ({
			getPreferences: mockGetPreferences,
			patchPreferences: mockPatchPreferences,
			savePreferences: mockSavePreferences
		})
	};
});

vi.mock('$lib/api/alertsService', () => ({
	alertsService: {
		getAlerts: vi.fn().mockResolvedValue({ items: [] }),
		createAlert: vi.fn().mockResolvedValue({}),
		deleteAlert: vi.fn().mockResolvedValue({})
	}
}));

vi.mock('$lib/api/notesService', () => ({
	notesService: {
		getNotes: vi.fn().mockResolvedValue({ items: [] })
	}
}));

vi.mock('$lib/api/documentsService', () => ({
	documentsService: {
		getDocuments: vi.fn().mockResolvedValue({ items: [] })
	}
}));

vi.mock('@/api/accountService', () => ({
	accountService: {
		getHoldings: vi.fn().mockResolvedValue({ items: [] })
	}
}));

vi.mock('$lib/components/watchlist/watchlistService.svelte', () => ({
	getWatchlistService: () => ({
		hasSecurity: vi.fn().mockReturnValue(false),
		toggleSecurity: vi.fn()
	})
}));

let mockChartProps: Record<string, unknown> | null = null;

vi.mock('$lib/components/charts/security-chart.svelte', () => {
	return {
		/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
		default: (...args: any[]) => {
			mockChartProps = args[1] ?? args[0];
			return null;
		}
	};
});

import { userPreferencesService } from '$lib/api/userPreferencesService';
import { alertsService } from '$lib/api/alertsService';

// ---------------------------------------------------------------------------
// Helpers under test — imported directly from the real module the page uses
// ---------------------------------------------------------------------------
import {
	mergeChartPreferences,
	displayCandlesFor,
	shouldForceRefetch,
	parseCandleTime,
	mergeCandles,
	shouldFetchMoreData,
	computeIndicatorData
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

// ---------------------------------------------------------------------------
// computeIndicatorData — timeframe-aware Day MA (ma50 / ma200)
// ---------------------------------------------------------------------------
describe('computeIndicatorData — Day Moving Averages (ma50 / ma200)', () => {
	function makeDailyCandles(): Candle[] {
		return [
			{ time: '2024-01-01', open: 10, high: 12, low: 9, close: 10, volume: 100 },
			{ time: '2024-01-02', open: 20, high: 22, low: 19, close: 20, volume: 200 },
			{ time: '2024-01-03', open: 30, high: 32, low: 29, close: 30, volume: 300 },
			{ time: '2024-01-04', open: 40, high: 42, low: 39, close: 40, volume: 400 },
			{ time: '2024-01-05', open: 50, high: 52, low: 49, close: 50, volume: 500 }
		];
	}

	it('computes Day MA on 1h interval using scaled rolling SMA (period * 7)', () => {
		const candles: Candle[] = Array.from({ length: 15 }, (_, i) => ({
			time: (1704067200 + i * 3600) as unknown as Time,
			open: 10,
			high: 12,
			low: 9,
			close: (i + 1) * 10,
			volume: 100
		}));
		const result = computeIndicatorData('ma50', { period: 2 }, candles, '1h') as {
			time: Time;
			value: number;
		}[];
		// 2-day MA on 1h -> effective period 14 bars. 15 candles -> 2 points (indices 13, 14)
		expect(result.length).toBe(2);
		expect(result[0]).toEqual({ time: 1704067200 + 13 * 3600, value: 75 });
		expect(result[1]).toEqual({ time: 1704067200 + 14 * 3600, value: 85 });
	});

	it('computes Day MA on 4h interval using scaled rolling SMA (period * 2)', () => {
		const candles: Candle[] = Array.from({ length: 5 }, (_, i) => ({
			time: (1704067200 + i * 14400) as unknown as Time,
			open: 10,
			high: 12,
			low: 9,
			close: (i + 1) * 10,
			volume: 100
		}));
		const result = computeIndicatorData('ma200', { period: 2 }, candles, '4h') as {
			time: Time;
			value: number;
		}[];
		// 2-day MA on 4h -> effective period 4 bars. 5 candles -> 2 points (indices 3, 4)
		expect(result.length).toBe(2);
		expect(result[0]).toEqual({ time: 1704067200 + 3 * 14400, value: 25 });
		expect(result[1]).toEqual({ time: 1704067200 + 4 * 14400, value: 35 });
	});

	it('computes Day MA on 1d interval using direct daily candles', () => {
		const candles = makeDailyCandles();
		const result = computeIndicatorData('ma50', { period: 3 }, candles, '1d') as {
			time: Time;
			value: number;
		}[];
		expect(result).toEqual([
			{ time: '2024-01-03', value: 20 },
			{ time: '2024-01-04', value: 30 },
			{ time: '2024-01-05', value: 40 }
		]);
	});

	it('computes Day MA on 1w interval by scaling period (period / 5)', () => {
		const weeklyCandles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 15, low: 9, close: 10, volume: 100 },
			{ time: '2024-01-08', open: 20, high: 25, low: 19, close: 20, volume: 200 },
			{ time: '2024-01-15', open: 30, high: 35, low: 29, close: 30, volume: 300 }
		];
		// period 10 / 5 = 2 weeks SMA
		const result = computeIndicatorData('ma50', { period: 10 }, weeklyCandles, '1w') as {
			time: Time;
			value: number;
		}[];
		expect(result).toEqual([
			{ time: '2024-01-08', value: 15 },
			{ time: '2024-01-15', value: 25 }
		]);
	});

	it('computes Day MA on 1m interval by scaling period (period / 21)', () => {
		const monthlyCandles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 15, low: 9, close: 10, volume: 100 },
			{ time: '2024-02-01', open: 20, high: 25, low: 19, close: 20, volume: 200 }
		];
		// period 21 / 21 = 1 month SMA
		const result = computeIndicatorData('ma50', { period: 21 }, monthlyCandles, '1m') as {
			time: Time;
			value: number;
		}[];
		expect(result).toEqual([
			{ time: '2024-01-01', value: 10 },
			{ time: '2024-02-01', value: 20 }
		]);
	});

	it('reads period from config.settings if not directly on config', () => {
		const candles = makeDailyCandles();
		const result = computeIndicatorData('ma50', { settings: { period: 2 } }, candles, '1d') as {
			time: Time;
			value: number;
		}[];
		expect(result.length).toBe(4);
		expect(result[0]).toEqual({ time: '2024-01-02', value: 15 });
	});
});

// ---------------------------------------------------------------------------
// computeIndicatorData — timeframe-aware Week MA (ma50w / ma200w)
// ---------------------------------------------------------------------------
describe('computeIndicatorData — Week Moving Averages (ma50w / ma200w)', () => {
	it('computes Week MA on 1d interval using scaled rolling SMA (period * 5)', () => {
		const candles: Candle[] = Array.from({ length: 12 }, (_, i) => ({
			time: `2024-01-${String(i + 1).padStart(2, '0')}`,
			open: 10,
			high: 12,
			low: 9,
			close: (i + 1) * 10,
			volume: 100
		}));
		const result = computeIndicatorData('ma50w', { period: 2 }, candles, '1d') as {
			time: Time;
			value: number;
		}[];
		// 2-week MA on 1d -> effective period 10 bars. 12 candles -> 3 points (indices 9, 10, 11)
		expect(result.length).toBe(3);
		expect(result[0]).toEqual({ time: '2024-01-10', value: 55 });
		expect(result[1]).toEqual({ time: '2024-01-11', value: 65 });
		expect(result[2]).toEqual({ time: '2024-01-12', value: 75 });
	});

	it('computes Week MA on 1h interval using scaled rolling SMA (period * 35)', () => {
		const candles: Candle[] = Array.from({ length: 72 }, (_, i) => ({
			time: (1704067200 + i * 3600) as unknown as Time,
			open: 10,
			high: 12,
			low: 9,
			close: (i + 1) * 10,
			volume: 100
		}));
		const result = computeIndicatorData('ma50w', { period: 2 }, candles, '1h') as {
			time: Time;
			value: number;
		}[];
		// 2-week MA on 1h -> effective period 70 bars. 72 candles -> 3 points (indices 69, 70, 71)
		expect(result.length).toBe(3);
		expect(result[0]).toEqual({ time: 1704067200 + 69 * 3600, value: 355 });
		expect(result[1]).toEqual({ time: 1704067200 + 70 * 3600, value: 365 });
		expect(result[2]).toEqual({ time: 1704067200 + 71 * 3600, value: 375 });
	});

	it('computes Week MA on 4h interval using scaled rolling SMA (period * 10)', () => {
		const candles: Candle[] = Array.from({ length: 22 }, (_, i) => ({
			time: (1704067200 + i * 14400) as unknown as Time,
			open: 10,
			high: 12,
			low: 9,
			close: (i + 1) * 10,
			volume: 100
		}));
		const result = computeIndicatorData('ma200w', { period: 2 }, candles, '4h') as {
			time: Time;
			value: number;
		}[];
		// 2-week MA on 4h -> effective period 20 bars. 22 candles -> 3 points (indices 19, 20, 21)
		expect(result.length).toBe(3);
		expect(result[0]).toEqual({ time: 1704067200 + 19 * 14400, value: 105 });
		expect(result[1]).toEqual({ time: 1704067200 + 20 * 14400, value: 115 });
		expect(result[2]).toEqual({ time: 1704067200 + 21 * 14400, value: 125 });
	});

	it('computes Week MA on 1w interval directly with SMA', () => {
		const weeklyCandles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 15, low: 9, close: 10, volume: 100 },
			{ time: '2024-01-08', open: 20, high: 25, low: 19, close: 20, volume: 200 },
			{ time: '2024-01-15', open: 30, high: 35, low: 29, close: 30, volume: 300 }
		];
		const result = computeIndicatorData('ma50w', { period: 2 }, weeklyCandles, '1w') as {
			time: Time;
			value: number;
		}[];
		expect(result).toEqual([
			{ time: '2024-01-08', value: 15 },
			{ time: '2024-01-15', value: 25 }
		]);
	});

	it('computes Week MA on 1m interval by scaling period (period * 12 / 52)', () => {
		const monthlyCandles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 15, low: 9, close: 10, volume: 100 },
			{ time: '2024-02-01', open: 20, high: 25, low: 19, close: 20, volume: 200 }
		];
		// period 4 * 12 / 52 ≈ 1 month SMA
		const result = computeIndicatorData('ma50w', { period: 4 }, monthlyCandles, '1m') as {
			time: Time;
			value: number;
		}[];
		expect(result).toEqual([
			{ time: '2024-01-01', value: 10 },
			{ time: '2024-02-01', value: 20 }
		]);
	});
});

// ---------------------------------------------------------------------------
// computeIndicatorData — Timestamp format preservation
// ---------------------------------------------------------------------------
describe('computeIndicatorData — Timestamp format preservation', () => {
	it('preserves UTCTimestamp seconds format for intraday series', () => {
		const candles: Candle[] = Array.from({ length: 14 }, (_, i) => ({
			time: (1704067200 + i * 3600) as unknown as Time,
			open: 10,
			high: 11,
			low: 9,
			close: 10 + i,
			volume: 100
		}));
		const result = computeIndicatorData('ma50', { period: 2 }, candles, '1h') as {
			time: Time;
			value: number;
		}[];
		expect(result.length).toBe(1);
		expect(typeof result[0].time).toBe('number');
		expect(result[0].time).toBe(1704067200 + 13 * 3600);
	});

	it('preserves ISO date strings for daily/weekly/monthly series', () => {
		const candles: Candle[] = [
			{ time: '2024-01-01', open: 10, high: 11, low: 9, close: 10, volume: 100 },
			{ time: '2024-01-02', open: 20, high: 21, low: 19, close: 20, volume: 100 }
		];
		const result = computeIndicatorData('ma50', { period: 2 }, candles, '1d') as {
			time: Time;
			value: number;
		}[];
		expect(typeof result[0].time).toBe('string');
		expect(result[0].time).toBe('2024-01-02');
	});
});

// ---------------------------------------------------------------------------
// computeIndicatorData — Chart style sensitivity (raw vs HA candles)
// ---------------------------------------------------------------------------
describe('computeIndicatorData — Chart style candle closes sensitivity', () => {
	const rawCandles: Candle[] = [
		{ time: '2024-01-01', open: 100, high: 110, low: 90, close: 100, volume: 500 },
		{ time: '2024-01-02', open: 100, high: 120, low: 95, close: 110, volume: 500 }
	];
	const haCandles: Candle[] = [
		{ time: '2024-01-01', open: 100, high: 110, low: 90, close: 105, volume: 500 },
		{ time: '2024-01-02', open: 102.5, high: 120, low: 95, close: 115, volume: 500 }
	];

	it('calculates indicators with raw candle closes when style is candlestick', () => {
		const activeCandles = displayCandlesFor('candlestick', rawCandles, haCandles);
		const result = computeIndicatorData('ma50', { period: 2 }, activeCandles, '1d') as {
			time: Time;
			value: number;
		}[];
		// (100 + 110) / 2 = 105
		expect(result[0].value).toBe(105);
	});

	it('calculates indicators with Heikin-Ashi candle closes when style is heikin_ashi', () => {
		const activeCandles = displayCandlesFor('heikin_ashi', rawCandles, haCandles);
		const result = computeIndicatorData('ma50', { period: 2 }, activeCandles, '1d') as {
			time: Time;
			value: number;
		}[];
		// (105 + 115) / 2 = 110
		expect(result[0].value).toBe(110);
	});
});

// ---------------------------------------------------------------------------
// computeIndicatorData — Non-MA indicators
// ---------------------------------------------------------------------------
describe('computeIndicatorData — Non-MA indicators', () => {
	const testCandles: Candle[] = [
		{ time: '2024-01-01', open: 10, high: 15, low: 9, close: 12, volume: 1000 },
		{ time: '2024-01-02', open: 12, high: 14, low: 8, close: 9, volume: 500 },
		{ time: '2024-01-03', open: 9, high: 16, low: 9, close: 15, volume: 800 },
		{ time: '2024-01-04', open: 15, high: 18, low: 13, close: 14, volume: 600 }
	];

	it('computes volume indicator with correct colors and volumes', () => {
		const result = computeIndicatorData('volume', {}, testCandles, '1d') as {
			time: Time;
			value: number;
			color: string;
		}[];
		expect(result.length).toBe(4);
		expect(result[0]).toEqual({ time: '2024-01-01', value: 1000, color: '#26a69a80' }); // close (12) >= open (10) -> green
		expect(result[1]).toEqual({ time: '2024-01-02', value: 500, color: '#ef535080' }); // close (9) < open (12) -> red
	});

	it('computes OBV indicator', () => {
		const result = computeIndicatorData('obv', {}, testCandles, '1d') as {
			time: Time;
			value: number;
		}[];
		expect(result.length).toBe(4);
		expect(result[0].value).toBe(1000);
		expect(result[1].value).toBe(500); // 1000 - 500
		expect(result[2].value).toBe(1300); // 500 + 800
	});

	it('computes RSI indicator with configurable period', () => {
		const result = computeIndicatorData('rsi', { period: 2 }, testCandles, '1d');
		expect(result.length).toBeGreaterThan(0);
	});

	it('computes MACD indicator with configurable fast/slow/signal', () => {
		const result = computeIndicatorData('macd', { fast: 2, slow: 3, signal: 2 }, testCandles, '1d');
		expect(result.length).toBeGreaterThan(0);
	});

	it('computes Bollinger Bands indicator with configurable period/stdDev', () => {
		const result = computeIndicatorData('bb', { period: 3, stdDev: 2 }, testCandles, '1d');
		expect(result.length).toBe(2);
	});

	it('returns empty array when candles array is empty', () => {
		expect(computeIndicatorData('volume', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('obv', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('rsi', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('macd', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('bb', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('ma50', {}, [], '1d')).toEqual([]);
		expect(computeIndicatorData('ma50w', {}, [], '1d')).toEqual([]);
	});
});

describe('Elliott Wave Preferences Serialization', () => {
	const sampleWaveCount: DegreeWaveCount = {
		points: [
			{ wave: 1, time: '2024-01-01', price: 100 },
			{ wave: 2, time: '2024-01-02', price: 80 },
			{ wave: 3, time: '2024-01-03', price: 150 },
			{ wave: 4, time: '2024-01-04', price: 120 },
			{ wave: 5, time: '2024-01-05', price: 200 }
		]
	};

	it('persists cycle wave counts under specific security id', () => {
		const updated = updateSecurityElliottWaves(null, 'sec-100', 'cycle', sampleWaveCount);
		expect(updated['sec-100'].cycle).toEqual(sampleWaveCount);
		expect(updated['sec-100'].primary).toBeUndefined();
	});

	it('persists primary wave count without clobbering cycle wave count', () => {
		const initial: Record<string, SecurityElliottWaves> = {
			'sec-100': { cycle: sampleWaveCount }
		};
		const primaryWave: DegreeWaveCount = {
			points: [{ wave: 1, time: '2024-02-01', price: 250 }]
		};
		const updated = updateSecurityElliottWaves(initial, 'sec-100', 'primary', primaryWave);
		expect(updated['sec-100'].cycle).toEqual(sampleWaveCount);
		expect(updated['sec-100'].primary).toEqual(primaryWave);
	});

	it('clears active degree wave count by setting to null', () => {
		const initial: Record<string, SecurityElliottWaves> = {
			'sec-100': { cycle: sampleWaveCount, primary: sampleWaveCount }
		};
		const updated = updateSecurityElliottWaves(initial, 'sec-100', 'cycle', null);
		expect(updated['sec-100'].cycle).toBeNull();
		expect(updated['sec-100'].primary).toEqual(sampleWaveCount);
	});
});

describe('Security Page - Elliott Wave Toolbar & Integration', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }]
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: {
				'sec-1': {
					cycle: { points: [{ wave: 1, time: '2024-01-01', price: 100 }] },
					primary: null
				}
			}
		});
	});

	it('renders Elliott Wave toolbar with Cycle, Primary, Draw Wave, and Clear buttons', async () => {
		render(PageComponent, { props: { data: mockData } });

		expect(await screen.findByRole('button', { name: /Select Cycle degree/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Select Primary degree/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Toggle drawing wave/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Clear wave count/i })).toBeInTheDocument();
	});

	it('allows toggling between Cycle and Primary degrees', async () => {
		render(PageComponent, { props: { data: mockData } });

		const cycleBtn = await screen.findByRole('button', { name: /Select Cycle degree/i });
		const primaryBtn = screen.getByRole('button', { name: /Select Primary degree/i });

		// Initially Cycle is active (has active styling)
		expect(cycleBtn.className).toContain('bg-primary');
		expect(primaryBtn.className).not.toContain('bg-primary');

		await fireEvent.click(primaryBtn);

		expect(primaryBtn.className).toContain('bg-primary');
		expect(cycleBtn.className).not.toContain('bg-primary');
	});

	it('toggles drawing mode on and off when Draw Wave button is clicked', async () => {
		render(PageComponent, { props: { data: mockData } });

		const drawBtn = await screen.findByRole('button', { name: /Toggle drawing wave/i });
		expect(drawBtn.textContent?.trim()).toBe('Draw Wave');

		await fireEvent.click(drawBtn);
		expect(drawBtn.textContent?.trim()).toBe('Drawing...');
		expect(drawBtn.className).toContain('bg-primary');

		await fireEvent.click(drawBtn);
		expect(drawBtn.textContent?.trim()).toBe('Draw Wave');
	});

	it('persists cleared wave count when Clear button is clicked', async () => {
		render(PageComponent, { props: { data: mockData } });

		const clearBtn = await screen.findByRole('button', { name: /Clear wave count/i });
		await fireEvent.click(clearBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith(
			expect.objectContaining({
				elliott_waves: expect.objectContaining({
					'sec-1': expect.objectContaining({
						cycle: null
					})
				})
			})
		);
	});

	it('clearing a wave does not re-fetch market prices', async () => {
		mockGetPrices.mockClear();
		render(PageComponent, { props: { data: mockData } });

		const clearBtn = await screen.findByRole('button', { name: /Clear wave count/i });
		await fireEvent.click(clearBtn);

		// Clearing wave should NOT invoke getPrices
		expect(mockGetPrices).not.toHaveBeenCalled();
	});

	it('drawing mode remains active when wave updates occur during sequential drawing', async () => {
		render(PageComponent, { props: { data: mockData } });

		const drawBtn = await screen.findByRole('button', { name: /Toggle drawing wave/i });
		await fireEvent.click(drawBtn);
		expect(drawBtn.textContent?.trim()).toBe('Drawing...');

		// Simulate wave point update / preference mutation occurring while in drawing mode
		vi.mocked(userPreferencesService.patchPreferences).mockResolvedValueOnce({});

		// Verify drawing mode remains active
		expect(screen.getByRole('button', { name: /Toggle drawing wave/i }).textContent?.trim()).toBe(
			'Drawing...'
		);
	});

	it('resets drawing mode on soft navigation to a different security', async () => {
		const { rerender } = render(PageComponent, { props: { data: mockData } });

		const drawBtn = await screen.findByRole('button', { name: /Toggle drawing wave/i });
		await fireEvent.click(drawBtn);
		expect(drawBtn.textContent?.trim()).toBe('Drawing...');

		// Soft navigate to another security
		const newSecurityData = {
			security: {
				id: 'sec-2',
				symbol: 'MSFT',
				name: 'Microsoft Corp.'
			},
			items: [{ date: '2024-01-01', open: 200, high: 210, low: 195, close: 205, volume: 2000 }]
		};

		await rerender({ data: newSecurityData });

		// Wait for soft navigation effect to execute and reset drawing mode
		await waitFor(() => {
			expect(screen.getByRole('button', { name: /Toggle drawing wave/i }).textContent?.trim()).toBe(
				'Draw Wave'
			);
		});
	});
});

describe('Security Page - Wave Selection & Keyboard Deletion', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }]
	};

	const initialWaves: Record<string, SecurityElliottWaves> = {
		'sec-1': {
			cycle: {
				points: [
					{ wave: 0, time: '2024-01-01', price: 50 },
					{ wave: 1, time: '2024-01-02', price: 100 },
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			},
			primary: {
				points: [
					{ wave: 0, time: '2024-01-01', price: 60 },
					{ wave: 1, time: '2024-01-02', price: 110 }
				]
			}
		}
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: initialWaves,
			wave_settings: {
				alert_percents: {
					cycle: { wave3: 90, wave5: 90 },
					primary: { wave3: null, wave5: null }
				}
			}
		});
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [
				{
					id: 101,
					security_id: 'sec-1',
					user_id: 'user-1',
					target_price: 135,
					condition: 'above',
					source: 'wave',
					triggered_at: null,
					created_at: '2024-01-01'
				}
			],
			total: 1,
			offset: 0,
			limit: 50
		});
		vi.mocked(alertsService.createAlert).mockResolvedValue({} as never);
		vi.mocked(alertsService.deleteAlert).mockResolvedValue(undefined);
	});

	it('selects wave degree when chart triggers onWaveSelect and passes selectedWaveDegree to chart', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Simulate selecting 'cycle'
		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('cycle');

		await waitFor(() => {
			// @ts-expect-error - mockChartProps typed as Record
			expect(mockChartProps.selectedWaveDegree).toBe('cycle');
		});
	});

	it('clears selected wave on Delete key press, patches user preferences, and reconciles alerts', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Select cycle wave
		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('cycle');

		// Press Delete on window
		await fireEvent.keyDown(window, { key: 'Delete' });

		// Preferences patched with cycle = null
		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith(
				expect.objectContaining({
					elliott_waves: expect.objectContaining({
						'sec-1': expect.objectContaining({
							cycle: null,
							primary: expect.any(Object)
						})
					})
				})
			);
		});

		// Alert reconciliation should have deleted the wave-source alert (id: 101)
		await waitFor(() => {
			expect(alertsService.deleteAlert).toHaveBeenCalledWith('sec-1', 101);
		});

		// Selection is reset to null
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBeNull();
	});

	it('clears selected wave on Backspace key press', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Select primary wave
		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('primary');

		// Press Backspace on window
		await fireEvent.keyDown(window, { key: 'Backspace' });

		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith(
				expect.objectContaining({
					elliott_waves: expect.objectContaining({
						'sec-1': expect.objectContaining({
							primary: null
						})
					})
				})
			);
		});

		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBeNull();
	});

	it('deselects wave and exits drawing mode on Escape key press', async () => {
		render(PageComponent, { props: { data: mockData } });
		const drawBtn = await screen.findByRole('button', { name: /Toggle drawing wave/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Enter drawing mode and select a wave
		await fireEvent.click(drawBtn);
		expect(drawBtn.textContent?.trim()).toBe('Drawing...');

		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('cycle');

		// Press Escape on window
		await fireEvent.keyDown(window, { key: 'Escape' });

		// Drawing mode should be exited and selected wave cleared
		expect(drawBtn.textContent?.trim()).toBe('Draw Wave');
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBeNull();
	});

	it('clears selection when chart emits onWaveSelect(null)', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('cycle');
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBe('cycle');

		// Click empty space
		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.(null);
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBeNull();
	});

	it('does not delete wave on Delete or Backspace when typing in an input element', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Select cycle wave
		// @ts-expect-error - mockChartProps typed as Record
		mockChartProps.onWaveSelect?.('cycle');

		// Create dummy input element
		const inputEl = document.createElement('input');
		document.body.appendChild(inputEl);
		inputEl.focus();

		// Trigger Delete and Backspace on input element
		await fireEvent.keyDown(inputEl, { key: 'Delete' });
		await fireEvent.keyDown(inputEl, { key: 'Backspace' });

		// Should NOT have triggered preferences patch for clearing wave
		expect(userPreferencesService.patchPreferences).not.toHaveBeenCalled();

		// Selection is preserved
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.selectedWaveDegree).toBe('cycle');

		document.body.removeChild(inputEl);
	});
});

describe('Fibonacci Preferences Serialization', () => {
	const sampleRetracement: FibRetracementDrawing = {
		p1: { time: '2024-01-01', price: 100 },
		p2: { time: '2024-01-02', price: 200 },
		visible: true
	};

	const sampleExtension: FibExtensionDrawing = {
		p1: { time: '2024-01-01', price: 100 },
		p2: { time: '2024-01-02', price: 200 },
		p3: { time: '2024-01-03', price: 150 },
		visible: true
	};

	it('persists retracement drawing under specific security id', () => {
		const updated = updateSecurityFibonacciTools(null, 'sec-100', 'retracement', sampleRetracement);
		expect(updated['sec-100'].retracement).toEqual(sampleRetracement);
		expect(updated['sec-100'].extension).toBeUndefined();
	});

	it('persists extension drawing without clobbering retracement drawing', () => {
		const initial: Record<string, SecurityFibonacciTools> = {
			'sec-100': { retracement: sampleRetracement }
		};
		const updated = updateSecurityFibonacciTools(initial, 'sec-100', 'extension', sampleExtension);
		expect(updated['sec-100'].retracement).toEqual(sampleRetracement);
		expect(updated['sec-100'].extension).toEqual(sampleExtension);
	});

	it('clears specific tool drawing by setting to null', () => {
		const initial: Record<string, SecurityFibonacciTools> = {
			'sec-100': { retracement: sampleRetracement, extension: sampleExtension }
		};
		const updated = updateSecurityFibonacciTools(initial, 'sec-100', 'retracement', null);
		expect(updated['sec-100'].retracement).toBeNull();
		expect(updated['sec-100'].extension).toEqual(sampleExtension);
	});

	it('clears all tools for security when null is passed', () => {
		const initial: Record<string, SecurityFibonacciTools> = {
			'sec-100': { retracement: sampleRetracement, extension: sampleExtension }
		};
		const updated = updateSecurityFibonacciTools(initial, 'sec-100', null);
		expect(updated['sec-100'].retracement).toBeNull();
		expect(updated['sec-100'].extension).toBeNull();
	});
});

describe('Security Page - Fibonacci Toolbar & Integration', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }]
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			fibonacci_tools: {
				'sec-1': {
					retracement: {
						p1: { time: '2024-01-01', price: 100 },
						p2: { time: '2024-01-02', price: 200 },
						visible: true
					},
					extension: null
				}
			}
		});
	});

	it('renders Fibonacci toolbar with Fib Retrace, Fib Extend, and Clear buttons, and Chart Settings icon button', async () => {
		render(PageComponent, { props: { data: mockData } });

		expect(
			await screen.findByRole('button', { name: /Toggle Fib Retrace drawing/i })
		).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Toggle Fib Extend drawing/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Clear Fibonacci drawing/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Open chart settings/i })).toBeInTheDocument();
	});

	it('toggles drawing mode on and off when Fib Retrace button is clicked and cancels wave drawing mode', async () => {
		render(PageComponent, { props: { data: mockData } });

		const retraceBtn = await screen.findByRole('button', { name: /Toggle Fib Retrace drawing/i });
		const drawWaveBtn = screen.getByRole('button', { name: /Toggle drawing wave/i });

		// Engage wave drawing first
		await fireEvent.click(drawWaveBtn);
		expect(drawWaveBtn.className).toContain('bg-primary');

		// Click Fib Retrace -> engages retracement and cancels wave drawing
		await fireEvent.click(retraceBtn);
		expect(retraceBtn.className).toContain('bg-primary');
		expect(drawWaveBtn.className).not.toContain('bg-primary');

		// Click Fib Retrace again -> toggles off
		await fireEvent.click(retraceBtn);
		expect(retraceBtn.className).not.toContain('bg-primary');
	});

	it('toggles drawing mode on and off when Fib Extend button is clicked and cancels wave drawing mode', async () => {
		render(PageComponent, { props: { data: mockData } });

		const extendBtn = await screen.findByRole('button', { name: /Toggle Fib Extend drawing/i });
		const drawWaveBtn = screen.getByRole('button', { name: /Toggle drawing wave/i });

		// Engage wave drawing first
		await fireEvent.click(drawWaveBtn);
		expect(drawWaveBtn.className).toContain('bg-primary');

		// Click Fib Extend -> engages extension and cancels wave drawing
		await fireEvent.click(extendBtn);
		expect(extendBtn.className).toContain('bg-primary');
		expect(drawWaveBtn.className).not.toContain('bg-primary');

		// Click Fib Extend again -> toggles off
		await fireEvent.click(extendBtn);
		expect(extendBtn.className).not.toContain('bg-primary');
	});

	it('opens Fibonacci settings inside modal when Settings button is clicked and tab is selected', async () => {
		render(PageComponent, { props: { data: mockData } });

		const settingsBtn = await screen.findByRole('button', { name: /Open chart settings/i });
		await fireEvent.click(settingsBtn);

		expect(screen.getByText('Chart Settings')).toBeInTheDocument();

		const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });
		await fireEvent.click(fibTab);

		expect(screen.getByTestId('fibonacci-settings-panel')).toBeInTheDocument();
		expect(screen.getByTestId('fib-level-row-0.618')).toBeInTheDocument();
	});

	it('persists updated levels when settings dialog toggles a level in Fibonacci tab', async () => {
		render(PageComponent, { props: { data: mockData } });

		const settingsBtn = await screen.findByRole('button', { name: /Open chart settings/i });
		await fireEvent.click(settingsBtn);

		expect(screen.getByText('Chart Settings')).toBeInTheDocument();

		const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });
		await fireEvent.click(fibTab);

		const row0618 = screen.getByTestId('fib-level-row-0.618');
		await fireEvent.click(row0618);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith(
			expect.objectContaining({
				fibonacci_tools: expect.objectContaining({
					'sec-1': expect.objectContaining({
						retracement: expect.objectContaining({
							levels: expect.arrayContaining([
								expect.objectContaining({ ratio: 0.618, enabled: false })
							])
						})
					})
				})
			})
		);
	});

	it('persists cleared Fibonacci drawing when Clear button is clicked', async () => {
		render(PageComponent, { props: { data: mockData } });

		const clearBtn = await screen.findByRole('button', { name: /Clear Fibonacci drawing/i });
		await fireEvent.click(clearBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith(
			expect.objectContaining({
				fibonacci_tools: expect.objectContaining({
					'sec-1': expect.objectContaining({
						retracement: null
					})
				})
			})
		);
	});

	it('clearing Fibonacci drawing does not re-fetch market prices', async () => {
		mockGetPrices.mockClear();
		render(PageComponent, { props: { data: mockData } });

		const clearBtn = await screen.findByRole('button', { name: /Clear Fibonacci drawing/i });
		await fireEvent.click(clearBtn);

		expect(mockGetPrices).not.toHaveBeenCalled();
	});

	it('resets Fibonacci drawing mode on soft navigation to a different security', async () => {
		const { rerender } = render(PageComponent, { props: { data: mockData } });

		const retraceBtn = await screen.findByRole('button', { name: /Toggle Fib Retrace drawing/i });
		await fireEvent.click(retraceBtn);
		expect(retraceBtn.className).toContain('bg-primary');

		// Soft navigate to another security
		const newSecurityData = {
			security: {
				id: 'sec-2',
				symbol: 'MSFT',
				name: 'Microsoft Corp.'
			},
			items: [{ date: '2024-01-01', open: 200, high: 210, low: 195, close: 205, volume: 2000 }]
		};

		await rerender({ data: newSecurityData });

		await waitFor(() => {
			expect(
				screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i }).className
			).not.toContain('bg-primary');
		});
	});
});

describe('Security Page - Viewport Containment & Scrolling Layout', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }]
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('constrains root container to viewport height preventing page vertical scrolling', async () => {
		const { container } = render(PageComponent, { props: { data: mockData } });
		const rootDiv = container.firstElementChild as HTMLElement;
		expect(rootDiv).not.toBeNull();
		expect(rootDiv.className).toContain('h-svh');
		expect(rootDiv.className).toContain('max-h-svh');
		expect(rootDiv.className).toContain('min-h-0');
		expect(rootDiv.className).toContain('overflow-hidden');
	});

	it('pins timeframe, waves, and style toolbar with shrink-0', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		const cycleBtn = screen.getByRole('button', { name: /Select Cycle degree/i });
		const toolbar = cycleBtn.closest('div.border-b');
		expect(toolbar).not.toBeNull();
		expect(toolbar?.className).toContain('shrink-0');
	});

	it('constrains chart column and chart container to min-h-0 overflow-hidden', async () => {
		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		const cycleBtn = screen.getByRole('button', { name: /Select Cycle degree/i });
		const chartColumn = cycleBtn.closest('div.flex-col');
		expect(chartColumn).not.toBeNull();
		expect(chartColumn?.className).toContain('min-h-0');
		expect(chartColumn?.className).toContain('flex-1');
		expect(chartColumn?.className).toContain('overflow-hidden');
	});

	it('constrains right actions sidebar to min-h-0 and configures Sidebar.Content with overflow-y-auto', async () => {
		const { container } = render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		const rightSidebar = container.querySelector('div.w-64');
		expect(rightSidebar).not.toBeNull();
		expect(rightSidebar?.className).toContain('min-h-0');
		expect(rightSidebar?.className).toContain('h-full');

		const sidebarContent = rightSidebar?.querySelector('[data-slot="sidebar-content"]');
		expect(sidebarContent).not.toBeNull();
		expect(sidebarContent?.className).toContain('min-h-0');
		expect(sidebarContent?.className).toContain('overflow-y-auto');
	});
});

describe('Security Page - Wave Target Alert Reconcile', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [
			{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 100, volume: 1000 },
			{ date: '2024-01-02', open: 100, high: 120, low: 95, close: 100, volume: 1000 }
		]
	};

	// Cycle: wave3 target 150, wave5 target 200; primary: wave3 target 120, wave5 target 160.
	const fullWaves: Record<string, SecurityElliottWaves> = {
		'sec-1': {
			cycle: {
				points: [
					{ wave: 0, time: '2024-01-01', price: 50 },
					{ wave: 1, time: '2024-01-02', price: 100 },
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			},
			primary: {
				points: [
					{ wave: 0, time: '2024-02-01', price: 40 },
					{ wave: 1, time: '2024-02-02', price: 90 },
					{ wave: 2, time: '2024-02-03', price: 70 },
					{ wave: 3, time: '2024-02-04', price: 120 },
					{ wave: 4, time: '2024-02-05', price: 100 },
					{ wave: 5, time: '2024-02-06', price: 160 }
				]
			}
		}
	};

	const bothDegreesPercents = {
		cycle: { wave3: 90, wave5: 90 },
		primary: { wave3: 50, wave5: 50 }
	};

	function waveAlert(
		over: Partial<import('$lib/api/alertsService').PriceAlert>
	): import('$lib/api/alertsService').PriceAlert {
		return {
			id: 1,
			security_id: 'sec-1',
			user_id: 'user-1',
			target_price: 135,
			condition: 'above',
			source: 'wave',
			triggered_at: null,
			created_at: '2024-01-01',
			...over
		};
	}

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [],
			total: 0,
			offset: 0,
			limit: 50
		});
		vi.mocked(alertsService.createAlert).mockResolvedValue({} as never);
		vi.mocked(alertsService.deleteAlert).mockResolvedValue(undefined);
	});

	it('drawing points 3 and 5 creates wave-source alerts for every configured degree', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: { alert_percents: bothDegreesPercents }
		});

		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		// currentPrice = last candle close = 100
		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Simulate the chart's wave change events
		await vi.waitFor(() => {
			// @ts-expect-error - mockChartProps typed as Record
			mockChartProps.onWaveChange?.('cycle', {
				points: [
					{ wave: 3, price: 150 },
					{ wave: 5, price: 200 }
				]
			});
			// @ts-expect-error - mockChartProps typed as Record
			mockChartProps.onWaveChange?.('primary', {
				points: [
					{ wave: 3, price: 120 },
					{ wave: 5, price: 160 }
				]
			});
		});

		await waitFor(() => {
			expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
				target_price: 135,
				condition: 'above',
				source: 'wave'
			});
		});

		expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
			target_price: 180,
			condition: 'above',
			source: 'wave'
		});
		expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
			target_price: 60,
			condition: 'below',
			source: 'wave'
		});
		expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
			target_price: 80,
			condition: 'below',
			source: 'wave'
		});
	});

	it('clearing waves deletes only wave-source alerts; manual alerts untouched', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: { alert_percents: bothDegreesPercents }
		});
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [
				waveAlert({ id: 10, target_price: 135, condition: 'above', source: 'wave' }),
				waveAlert({ id: 11, target_price: 180, condition: 'above', source: 'wave' }),
				waveAlert({ id: 20, target_price: 135, condition: 'above', source: 'manual' })
			],
			total: 3,
			offset: 0,
			limit: 50
		});

		render(PageComponent, { props: { data: mockData } });

		const clearBtn = await screen.findByRole('button', { name: /Clear wave count/i });
		await fireEvent.click(clearBtn);

		// Clearing cycle deletes the two wave-source alerts, never the manual one.
		await waitFor(() => {
			expect(alertsService.deleteAlert).toHaveBeenCalledWith('sec-1', 10);
			expect(alertsService.deleteAlert).toHaveBeenCalledWith('sec-1', 11);
		});
		const manualIdCalls = vi
			.mocked(alertsService.deleteAlert)
			.mock.calls.filter(([, id]) => id === 20);
		expect(manualIdCalls).toHaveLength(0);
	});

	it('initial load with matching pre-existing wave alerts is a no-op (idempotent)', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: { alert_percents: bothDegreesPercents }
		});
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [
				waveAlert({ id: 1, target_price: 135, condition: 'above', source: 'wave' }),
				waveAlert({ id: 2, target_price: 180, condition: 'above', source: 'wave' }),
				waveAlert({ id: 3, target_price: 60, condition: 'below', source: 'wave' }),
				waveAlert({ id: 4, target_price: 80, condition: 'below', source: 'wave' })
			],
			total: 4,
			offset: 0,
			limit: 50
		});

		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });

		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Give any (nonexistent) reconcile a chance to run.
		await new Promise((r) => setTimeout(r, 50));

		expect(alertsService.createAlert).not.toHaveBeenCalled();
		expect(alertsService.deleteAlert).not.toHaveBeenCalled();
	});

	it('percent change regenerates: deletes stale levels and creates new ones; manual untouched', async () => {
		// Load with percents A, whose alerts exist.
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: { alert_percents: bothDegreesPercents }
		});
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [
				waveAlert({ id: 1, target_price: 135, condition: 'above', source: 'wave' }),
				waveAlert({ id: 2, target_price: 180, condition: 'above', source: 'wave' }),
				waveAlert({ id: 3, target_price: 60, condition: 'below', source: 'wave' }),
				waveAlert({ id: 4, target_price: 80, condition: 'below', source: 'wave' }),
				waveAlert({ id: 20, target_price: 135, condition: 'above', source: 'manual' })
			],
			total: 5,
			offset: 0,
			limit: 50
		});

		const { unmount } = render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		// Reconcile on initial load is a no-op (alerts match percents A). Now remount with
		// percents B (e.g. cycle wave3 80 → 120, wave5 70 → 140) and stale A alerts present.
		unmount();
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [
				waveAlert({ id: 1, target_price: 135, condition: 'above', source: 'wave' }),
				waveAlert({ id: 2, target_price: 180, condition: 'above', source: 'wave' }),
				waveAlert({ id: 20, target_price: 135, condition: 'above', source: 'manual' })
			],
			total: 3,
			offset: 0,
			limit: 50
		});
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: {
				alert_percents: {
					cycle: { wave3: 80, wave5: 70 },
					primary: { wave3: null, wave5: null }
				}
			}
		});
		vi.mocked(alertsService.createAlert).mockResolvedValue({} as never);
		vi.mocked(alertsService.deleteAlert).mockResolvedValue(undefined);

		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		await waitFor(() => {
			expect(alertsService.deleteAlert).toHaveBeenCalledWith('sec-1', 1);
			expect(alertsService.deleteAlert).toHaveBeenCalledWith('sec-1', 2);
		});
		// New desired: cycle wave3 150×80%=120 (above), wave5 200×70%=140 (above)
		expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
			target_price: 120,
			condition: 'above',
			source: 'wave'
		});
		expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
			target_price: 140,
			condition: 'above',
			source: 'wave'
		});
		// Manual alert never deleted nor re-created.
		const manualIdCalls = vi
			.mocked(alertsService.deleteAlert)
			.mock.calls.filter(([, id]) => id === 20);
		expect(manualIdCalls).toHaveLength(0);
	});

	it('all percents null with waves present → no alerts created', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: {
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			}
		});

		render(PageComponent, { props: { data: mockData } });
		await screen.findByRole('button', { name: /Select Cycle degree/i });
		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});

		await new Promise((r) => setTimeout(r, 50));

		expect(alertsService.createAlert).not.toHaveBeenCalled();
		expect(alertsService.deleteAlert).not.toHaveBeenCalled();
	});
});

describe('Security Page - Chart Settings Modal & Wave Settings Integration', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [
			{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 100, volume: 1000 },
			{ date: '2024-01-02', open: 100, high: 120, low: 95, close: 100, volume: 1000 }
		]
	};

	const fullWaves: Record<string, SecurityElliottWaves> = {
		'sec-1': {
			cycle: {
				points: [
					{ wave: 0, time: '2024-01-01', price: 50 },
					{ wave: 1, time: '2024-01-02', price: 100 },
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			}
		}
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			elliott_waves: fullWaves,
			wave_settings: {
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			}
		});
		vi.mocked(alertsService.getAlerts).mockResolvedValue({
			items: [],
			total: 0,
			offset: 0,
			limit: 50
		});
		vi.mocked(alertsService.createAlert).mockResolvedValue({} as never);
		vi.mocked(alertsService.deleteAlert).mockResolvedValue(undefined);
	});

	it('opens Chart Settings modal on Settings icon button click', async () => {
		render(PageComponent, { props: { data: mockData } });

		const settingsBtn = await screen.findByRole('button', { name: /Open chart settings/i });
		await fireEvent.click(settingsBtn);

		expect(screen.getByText('Chart Settings')).toBeInTheDocument();
		expect(screen.getByTestId('waves-settings-panel')).toBeInTheDocument();
	});

	it('persists wave settings and propagates snapToWicks prop to SecurityChart', async () => {
		render(PageComponent, { props: { data: mockData } });

		await screen.findByRole('button', { name: /Open chart settings/i });
		await waitFor(() => {
			expect(mockChartProps).not.toBeNull();
		});
		// @ts-expect-error - mockChartProps typed as Record
		expect(mockChartProps.snapToWicks).toBe(false);

		const settingsBtn = screen.getByRole('button', { name: /Open chart settings/i });
		await fireEvent.click(settingsBtn);

		const snapCheckbox = screen.getByTestId('snap-to-wicks-checkbox');
		await fireEvent.click(snapCheckbox);

		const saveBtn = screen.getByTestId('save-waves-btn');
		await fireEvent.click(saveBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			wave_settings: {
				snap_to_wicks: true,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			}
		});

		await waitFor(() => {
			// @ts-expect-error - mockChartProps typed as Record
			expect(mockChartProps.snapToWicks).toBe(true);
		});
	});

	it('saving wave alert percents in settings modal triggers scheduleWaveAlertsReconcile to create wave alerts', async () => {
		render(PageComponent, { props: { data: mockData } });

		const settingsBtn = await screen.findByRole('button', { name: /Open chart settings/i });
		await fireEvent.click(settingsBtn);

		const cycle3Input = screen.getByTestId('cycle-wave3-input');
		await fireEvent.input(cycle3Input, { target: { value: '90' } });

		const saveBtn = screen.getByTestId('save-waves-btn');
		await fireEvent.click(saveBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			wave_settings: {
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: 90, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			}
		});

		// 150 * 0.9 = 135 (above current price 100)
		await waitFor(() => {
			expect(alertsService.createAlert).toHaveBeenCalledWith('sec-1', {
				target_price: 135,
				condition: 'above',
				source: 'wave'
			});
		});
	});
});

describe('Security Page - Top Toolbar', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let PageComponent: Component<any>;

	const mockData = {
		security: {
			id: 'sec-1',
			symbol: 'AAPL',
			name: 'Apple Inc.'
		},
		items: [{ date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000 }]
	};

	beforeAll(async () => {
		const mod = await import('./+page.svelte');
		PageComponent = mod.default;
	}, 30000);

	beforeEach(() => {
		vi.clearAllMocks();
		mockChartProps = null;
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({});
	});

	it('renders timeframe buttons without "Timeframe:" text label', async () => {
		render(PageComponent, { props: { data: mockData } });

		expect(await screen.findByRole('button', { name: '1H' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: '4H' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: '1D' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: '1W' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: '1M' })).toBeInTheDocument();

		expect(screen.queryByText(/Timeframe:/i)).not.toBeInTheDocument();
	});

	it('renders toolbar without "Style:" text label', async () => {
		render(PageComponent, { props: { data: mockData } });

		await screen.findByRole('button', { name: '1D' });
		expect(screen.queryByText(/Style:/i)).not.toBeInTheDocument();
	});

	it('renders Candlestick and Heikin-Ashi icon buttons with aria-label and title', async () => {
		render(PageComponent, { props: { data: mockData } });

		const candleBtn = await screen.findByRole('button', { name: 'Candlestick' });
		expect(candleBtn).toBeInTheDocument();
		expect(candleBtn).toHaveAttribute('title', 'Candlestick');

		const haBtn = screen.getByRole('button', { name: 'Heikin-Ashi' });
		expect(haBtn).toBeInTheDocument();
		expect(haBtn).toHaveAttribute('title', 'Heikin-Ashi');
	});

	it('clicking Candlestick icon button sets chartStyle to candlestick and persists preference', async () => {
		render(PageComponent, { props: { data: mockData } });

		const candleBtn = await screen.findByRole('button', { name: 'Candlestick' });
		const haBtn = screen.getByRole('button', { name: 'Heikin-Ashi' });

		// Initial state is heikin_ashi
		expect(haBtn.className).toContain('bg-primary');
		expect(candleBtn.className).not.toContain('bg-primary');

		await fireEvent.click(candleBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			chart_style: 'candlestick'
		});
		expect(candleBtn.className).toContain('bg-primary');
		expect(haBtn.className).not.toContain('bg-primary');
	});

	it('clicking Heikin-Ashi icon button sets chartStyle to heikin_ashi and persists preference', async () => {
		render(PageComponent, { props: { data: mockData } });

		const candleBtn = await screen.findByRole('button', { name: 'Candlestick' });
		const haBtn = screen.getByRole('button', { name: 'Heikin-Ashi' });

		// First switch to candlestick
		await fireEvent.click(candleBtn);
		expect(candleBtn.className).toContain('bg-primary');

		vi.clearAllMocks();

		// Then switch back to heikin_ashi
		await fireEvent.click(haBtn);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			chart_style: 'heikin_ashi'
		});
		expect(haBtn.className).toContain('bg-primary');
		expect(candleBtn.className).not.toContain('bg-primary');
	});
});
