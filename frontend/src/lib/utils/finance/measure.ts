import type { DrawingPoint } from './drawings';

/**
 * Direction of a two-point measurement. Used to pick the label/line colour
 * (up = positive move, down = negative move, flat = no change).
 */
export type MeasureDirection = 'up' | 'down' | 'flat';

export interface MeasureComputation {
	/** Absolute price change: `p2.price - p1.price`. */
	delta: number;
	/** Percentage change relative to the first point: `delta / p1.price * 100`. */
	percent: number;
	direction: MeasureDirection;
}

/**
 * Computes the height/value of a move between two anchors.
 *
 * Percentage is always relative to the first point. When `p1.price` is zero the
 * percentage is undefined and falls back to `0` (the absolute delta and
 * direction are still reported).
 */
export function computeMeasure(p1: DrawingPoint, p2: DrawingPoint): MeasureComputation {
	const delta = p2.price - p1.price;
	const direction: MeasureDirection = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
	const percent = p1.price !== 0 && Number.isFinite(delta) ? (delta / p1.price) * 100 : 0;
	return { delta, percent, direction };
}

function formatSigned(value: number, fractionDigits: number): string {
	if (!Number.isFinite(value)) return (0).toFixed(fractionDigits);
	const fixed = value.toFixed(fractionDigits);
	// Normalize values that round to zero (including "-0.00") to an unsigned zero.
	if (Number(fixed) === 0) return (0).toFixed(fractionDigits);
	return value > 0 ? `+${fixed}` : fixed;
}

/**
 * Formats a measurement as an absolute change plus a percentage, both signed,
 * e.g. `"+2.31 (+4.6%)"` for a rise and `"-2.31 (-4.6%)"` for a fall.
 */
export function formatMeasureLabel(delta: number, percent: number): string {
	return `${formatSigned(delta, 2)} (${formatSigned(percent, 1)}%)`;
}

/** Convenience wrapper computing and formatting in one call. */
export function formatMeasureLabelForPoints(p1: DrawingPoint, p2: DrawingPoint): string {
	const { delta, percent } = computeMeasure(p1, p2);
	return formatMeasureLabel(delta, percent);
}
