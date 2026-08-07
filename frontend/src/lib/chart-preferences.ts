import type { ChartStyle, UserPreferences } from '$lib/api/userPreferencesService';
import type { Candle } from '@/utils/finance/candle';

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
