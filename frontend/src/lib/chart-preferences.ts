import type { ChartStyle, UserPreferences } from '$lib/api/userPreferencesService';
import type { Candle } from '@/utils/finance/candle';
import type { Time } from 'lightweight-charts';

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
