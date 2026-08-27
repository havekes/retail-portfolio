import type { Candle } from '@/utils/finance/candle';
import { parseCandleTime } from '$lib/chart-preferences';
import type { RewindSnapshot } from '$lib/utils/finance/rewind';

export interface TimelineDomain {
	first: number;
	last: number;
}

/**
 * Filters candles to only include those at or before the given cutoff date.
 * Returns the original candles array if cutoff is null or invalid.
 */
export function sliceCandlesBefore(candles: Candle[], cutoff: Date | null): Candle[] {
	if (!cutoff || isNaN(cutoff.getTime())) {
		return candles;
	}
	const cutoffMs = cutoff.getTime();
	return candles.filter((c) => {
		const t = parseCandleTime(c.time).getTime();
		return !isNaN(t) && t <= cutoffMs;
	});
}

/**
 * Computes the epoch-ms domain [first, last] for the rewind timeline.
 * `first` is the epoch-ms of the oldest snapshot (snapshots[0].captured_at).
 * `last` is the epoch-ms of `now`.
 * Guards against `last <= first` (e.g. single snapshot or now <= first) by setting `last = first + 1`.
 */
export function snapshotTimelineDomain(snapshots: RewindSnapshot[], now: Date): TimelineDomain {
	const first =
		snapshots.length > 0 && !isNaN(Date.parse(snapshots[0].captured_at))
			? Date.parse(snapshots[0].captured_at)
			: now.getTime();
	let last = now.getTime();
	if (isNaN(last)) {
		last = first + 1;
	}
	if (last <= first) {
		last = first + 1;
	}
	return { first, last };
}

/**
 * Maps a timestamp (epoch-ms or Date) to a proportional fraction [0, 1] over [first, last].
 * Clamps values outside [first, last] to [0, 1].
 */
export function timeToFraction(t: number | Date, first: number, last: number): number {
	const timeMs = typeof t === 'number' ? t : t.getTime();
	if (last <= first || isNaN(timeMs)) {
		return 0;
	}
	const fraction = (timeMs - first) / (last - first);
	return Math.max(0, Math.min(1, fraction));
}

/**
 * Maps a proportional fraction [0, 1] back to a Date within [first, last].
 * Clamps fraction to [0, 1].
 */
export function fractionToTime(f: number, first: number, last: number): Date {
	const clamped = Math.max(0, Math.min(1, f));
	return new Date(Math.round(first + clamped * (last - first)));
}
