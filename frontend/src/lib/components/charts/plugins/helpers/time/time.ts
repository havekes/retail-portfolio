import type { BusinessDay, Time, UTCTimestamp } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';

/** Convert any lightweight-charts Time value to epoch seconds (UTC). */
export function timeToEpochSeconds(time: Time): number {
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
	if (typeof reference === 'number') return epoch as UTCTimestamp;
	if (typeof reference === 'string') {
		// Date-only (YYYY-MM-DD) candles should stay date-only.
		return new Date(epoch * 1000).toISOString().slice(0, 10);
	}
	const d = new Date(epoch * 1000);
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
export function barsBetweenTimes(from: Time, to: Time, intervalSeconds: number): number {
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
