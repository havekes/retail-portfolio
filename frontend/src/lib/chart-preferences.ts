import type { ChartStyle, UserPreferences } from '$lib/api/userPreferencesService';
import type { Candle } from '@/utils/finance/candle';
import type { Time } from 'lightweight-charts';
import {
	calculateDayMA,
	calculateWeekMA,
	calculateSMA,
	type MASeries
} from '$lib/utils/finance/moving-average';
import { calculateOBV, type OBVSeries } from '$lib/utils/finance/obv';
import { calculateRSI, type RSISeries } from '$lib/utils/finance/rsi';
import { calculateMACD, type MACDSeries } from '$lib/utils/finance/macd';
import { calculateBollingerBands, type BBSeries } from '$lib/utils/finance/bollinger-bands';

export interface IndicatorComputeConfig {
	period?: number;
	fast?: number;
	slow?: number;
	signal?: number;
	stdDev?: number;
	settings?: Record<string, unknown>;
}

export type VolumeSeriesItem = {
	time: Time;
	value: number;
	color: string;
};

export type IndicatorSeriesData =
	MASeries | OBVSeries | RSISeries | MACDSeries | BBSeries | VolumeSeriesItem[];

/**
 * Computes chart-compatible series data for any supported indicator ID,
 * applying timeframe-aware moving averages (calculateDayMA / calculateWeekMA)
 * and user-supplied or default configurations.
 */
export function computeIndicatorData(
	indicatorId: string,
	config: Partial<IndicatorComputeConfig> | undefined,
	candles: Candle[],
	interval: string = '1d'
): IndicatorSeriesData {
	if (!candles || candles.length === 0) {
		return [];
	}

	const period =
		(config?.period as number | undefined) ?? (config?.settings?.period as number | undefined);

	switch (indicatorId) {
		case 'volume':
			return candles.map((c) => ({
				time: c.time,
				value: c.volume || 0,
				color: c.close >= c.open ? '#26a69a80' : '#ef535080'
			}));

		case 'obv':
			return calculateOBV(candles);

		case 'rsi':
			return calculateRSI(candles, { period: period ?? 14 });

		case 'macd': {
			const fast =
				(config?.fast as number | undefined) ??
				(config?.settings?.fast as number | undefined) ??
				12;
			const slow =
				(config?.slow as number | undefined) ??
				(config?.settings?.slow as number | undefined) ??
				26;
			const signal =
				(config?.signal as number | undefined) ??
				(config?.settings?.signal as number | undefined) ??
				9;
			return calculateMACD(candles, { fast, slow, signal });
		}

		case 'bb': {
			const stdDev =
				(config?.stdDev as number | undefined) ??
				(config?.settings?.stdDev as number | undefined) ??
				2;
			return calculateBollingerBands(candles, {
				period: period ?? 20,
				stdDev
			});
		}

		case 'ma50':
			return calculateDayMA(candles, interval, period ?? 50);

		case 'ma200':
			return calculateDayMA(candles, interval, period ?? 200);

		case 'ma50w':
			return calculateWeekMA(candles, interval, period ?? 50);

		case 'ma200w':
			return calculateWeekMA(candles, interval, period ?? 200);

		default:
			return calculateSMA(candles, period ?? 14);
	}
}

/**
 * Merges a partial preferences update into the full blob, preserving
 * the `indicators` key. This is the read-merge-write helper used by
 * the security page to persist chart preferences without clobbering
 * indicator settings.
 */
export function mergeChartPreferences(
	prefs: UserPreferences,
	partial: Partial<UserPreferences>
): UserPreferences {
	return {
		...prefs,
		indicators: prefs.indicators ?? {},
		...partial
	};
}

/**
 * Returns the candle array to display based on the active chart style.
 * 'heikin_ashi' → HA-transformed candles; 'candlestick' → raw candles.
 */
export function displayCandlesFor(style: ChartStyle, raw: Candle[], ha: Candle[]): Candle[] {
	return style === 'heikin_ashi' ? ha : raw;
}

/**
 * Decides whether a timeframe change should force a refetch even when
 * the requested interval matches the current `selectedInterval`.
 */
export function shouldForceRefetch(
	selectedInterval: string,
	interval: string,
	force: boolean
): boolean {
	if (force) return true;
	return selectedInterval !== interval;
}

/**
 * Converts a Lightweight Charts `Time` value to a standard JavaScript `Date` object.
 * Handles UTCTimestamp (number in seconds), string dates ("YYYY-MM-DD" or ISO string),
 * and BusinessDay objects.
 */
export function parseCandleTime(time: Time): Date {
	if (typeof time === 'number') {
		return new Date(time * 1000);
	}
	if (typeof time === 'string') {
		if (time.includes('-')) {
			const datePart = time.split('T')[0];
			const parts = datePart.split('-').map(Number);
			if (parts.length === 3 && !isNaN(parts[0]) && !isNaN(parts[1]) && !isNaN(parts[2])) {
				return new Date(parts[0], parts[1] - 1, parts[2]);
			}
		}
		return new Date(time);
	}
	if (typeof time === 'object' && time !== null && 'year' in time) {
		const t = time as { year: number; month: number; day: number };
		return new Date(t.year, t.month - 1, t.day);
	}
	return new Date(String(time));
}

/**
 * Merges incoming prepended candles with existing candles, filtering out duplicates
 * based on candle timestamp/date. Returns the merged array and count of added candles.
 */
export function mergeCandles(
	existing: Candle[],
	incoming: Candle[]
): { merged: Candle[]; addedCount: number } {
	const existingTimes = new Set(existing.map((c) => String(c.time)));
	const deduplicated = incoming.filter((c) => !existingTimes.has(String(c.time)));
	return {
		merged: [...deduplicated, ...existing],
		addedCount: deduplicated.length
	};
}

/**
 * Helper to check whether pagination fetch should proceed.
 */
export function shouldFetchMoreData(
	isLoadingMore: boolean,
	hasMoreData: boolean,
	securityId?: string,
	candleCount?: number
): boolean {
	if (isLoadingMore || !hasMoreData || !securityId || !candleCount || candleCount === 0) {
		return false;
	}
	return true;
}
