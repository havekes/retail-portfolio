import type { BusinessDay, Time, UTCTimestamp, WhitespaceData } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';

export const DEFAULT_FUTURE_BARS = 100;

/** Convert any lightweight-charts Time value to epoch seconds (UTC). */
export function timeToEpochSeconds(time: Time | number): number {
	if (typeof time === 'number') return time;
	if (typeof time === 'string') {
		const ms = new Date(time).getTime();
		return Number.isNaN(ms) ? 0 : Math.floor(ms / 1000);
	}
	if (time !== null && typeof time === 'object') {
		return Math.floor(Date.UTC(time.year, time.month - 1, time.day) / 1000);
	}
	return 0;
}

/** Rebuild a Time value in the same shape as `reference` from an epoch-seconds value. */
export function epochSecondsToTime(epoch: number, reference: Time): Time {
	const roundedEpoch = Math.round(epoch);
	if (typeof reference === 'number') return roundedEpoch as UTCTimestamp;
	if (typeof reference === 'string') {
		// Date-only (YYYY-MM-DD) candles should stay date-only.
		return new Date(roundedEpoch * 1000).toISOString().slice(0, 10);
	}
	const d = new Date(roundedEpoch * 1000);
	return {
		year: d.getUTCFullYear(),
		month: d.getUTCMonth() + 1,
		day: d.getUTCDate()
	} as BusinessDay;
}

/**
 * Add `n * intervalSeconds` to a reference Time, preserving the reference's
 * format so round-tripped future timestamps stay consistent with existing data.
 */
export function addIntervalToTime(reference: Time, n: number, intervalSeconds: number): Time {
	return epochSecondsToTime(timeToEpochSeconds(reference) + n * intervalSeconds, reference);
}

/** Number of whole bars between two Time values for the given interval (>= 0). */
export function barsBetweenTimes(
	from: Time | number,
	to: Time | number,
	intervalSeconds: number
): number {
	const diff = timeToEpochSeconds(to) - timeToEpochSeconds(from);
	return Math.max(0, Math.round(diff / intervalSeconds));
}

/**
 * Derive the bar interval in seconds from the median spacing of the most
 * recent candles. Falls back to the spacing between the last two candles.
 */
export function computeIntervalSeconds(candles: Candle[], sampleSize = 8): number {
	const times = candles.map((c) => timeToEpochSeconds(c.time));
	if (times.length < 2) return 0;

	const start = Math.max(0, times.length - sampleSize);
	const spacings: number[] = [];
	for (let i = start + 1; i < times.length; i++) {
		const diff = times[i] - times[i - 1];
		if (diff > 0) spacings.push(diff);
	}
	if (spacings.length === 0) return 0;

	spacings.sort((a, b) => a - b);
	const mid = Math.floor(spacings.length / 2);
	return spacings.length % 2 === 0 ? (spacings[mid - 1] + spacings[mid]) / 2 : spacings[mid];
}

export interface ResolvedAnchor {
	/** The candle's own Time value (date string, BusinessDay or epoch), in its native shape. */
	time: Time;
	/** Index of the resolved candle within the provided array. */
	index: number;
}

/**
 * Snap an epoch-seconds anchor to the candles of the *current* timeframe.
 *
 * Anchors are canonical epoch seconds; the chart data is keyed with whatever
 * shape the active timeframe uses (epoch for intraday, date strings for
 * daily/weekly/monthly). This resolves an anchor to the candle at or
 * immediately before it, so a date drawn on the daily chart lands on the
 * containing bar on every other timeframe.
 *
 * - Returns the first candle when the anchor predates it (clamped).
 * - Returns `null` when the anchor falls *after* the last candle (the caller
 *   projects it into the future whitespace instead) or when there is no data.
 */
export function resolveAnchorEpoch(
	candles: Candle[] | undefined,
	epoch: number
): ResolvedAnchor | null {
	if (!candles || candles.length === 0 || !Number.isFinite(epoch)) return null;

	const firstEpoch = timeToEpochSeconds(candles[0].time);
	const lastIndex = candles.length - 1;
	const lastEpoch = timeToEpochSeconds(candles[lastIndex].time);

	if (epoch > lastEpoch) return null;
	if (epoch <= firstEpoch) return { time: candles[0].time, index: 0 };

	// Binary search for the greatest candle with time <= epoch. Using
	// at-or-before (rather than a fixed [start, start+interval) window) keeps
	// snapping correct for irregular spacing (weekends, short months).
	let lo = 0;
	let hi = lastIndex;
	while (lo < hi) {
		const mid = Math.ceil((lo + hi) / 2);
		if (timeToEpochSeconds(candles[mid].time) <= epoch) {
			lo = mid;
		} else {
			hi = mid - 1;
		}
	}
	return { time: candles[lo].time, index: lo };
}

/**
 * Generate whitespace data points extending into the future beyond the last candle.
 * Returns an empty array if candles array has fewer than 2 items, count is non-positive,
 * or the calculated interval is non-positive.
 */
export function generateFutureWhitespace(
	candles: Candle[],
	count = DEFAULT_FUTURE_BARS
): WhitespaceData[] {
	if (candles.length < 2 || count <= 0) return [];
	const interval = computeIntervalSeconds(candles);
	if (interval <= 0) return [];

	const lastTime = candles[candles.length - 1].time;
	const whitespace: WhitespaceData[] = [];
	for (let i = 1; i <= count; i++) {
		whitespace.push({
			time: addIntervalToTime(lastTime, i, interval)
		});
	}
	return whitespace;
}
