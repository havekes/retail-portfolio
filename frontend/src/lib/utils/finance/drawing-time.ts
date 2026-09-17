import type { Time, UTCTimestamp } from 'lightweight-charts';

/**
 * Normalizes any lightweight-charts `Time` anchor (epoch number, ISO date
 * string or `BusinessDay` object) into canonical epoch seconds (UTC).
 *
 * Drawing anchors are stored in time, not timeframe-local bar indices, so a
 * drawing created on one timeframe keeps its dates and labels on every other.
 * Persisted drawings created before that invariant hold date strings or
 * `BusinessDay` objects; this normalizer upgrades them on load.
 *
 * Invalid/missing values fall back to `0`, mirroring the plugins'
 * `timeToEpochSeconds` helper. `$lib/utils/finance` is the lowest layer and
 * must not import from `plugins/helpers/`, so the conversion lives here.
 */
export function normalizeDrawingTime(time: Time | number | null | undefined): UTCTimestamp {
	if (typeof time === 'number') return time as UTCTimestamp;
	if (typeof time === 'string') {
		const ms = new Date(time).getTime();
		return (Number.isNaN(ms) ? 0 : Math.floor(ms / 1000)) as UTCTimestamp;
	}
	if (time !== null && time !== undefined && typeof time === 'object') {
		return Math.floor(Date.UTC(time.year, time.month - 1, time.day) / 1000) as UTCTimestamp;
	}
	return 0 as UTCTimestamp;
}
