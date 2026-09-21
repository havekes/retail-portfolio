import type { DrawingPoint } from './drawings';

/**
 * Direction of a two-point measurement. Used to pick the label/line colour
 * (up = positive move, down = negative move, flat = no change).
 */
export type MeasureDirection = 'up' | 'down' | 'flat';

export type MeasureSnapAngle = 'horizontal' | 'vertical' | 'diagonal';

export interface Point2D {
	x: number;
	y: number;
}

export interface MeasureComputation {
	/** Absolute price change: `p2.price - p1.price`. */
	delta: number;
	/** Percentage change relative to the first point: `delta / p1.price * 100`. */
	percent: number;
	direction: MeasureDirection;
}

export interface MeasureMetrics {
	bars?: number;
	elapsedSeconds?: number;
	elapsed?: string;
}

/**
 * Snaps a two-point vector to horizontal or vertical if within `thresholdDegrees`
 * of that axis; otherwise preserves diagonal measurement.
 */
export function snapMeasureAngle(
	p1: Point2D,
	p2: Point2D,
	thresholdDegrees: number = 15
): MeasureSnapAngle {
	const dx = Math.abs(p2.x - p1.x);
	const dy = Math.abs(p2.y - p1.y);

	if (dx === 0 && dy === 0) {
		return 'diagonal';
	}

	const angleRad = Math.atan2(dy, dx);
	const angleDeg = (angleRad * 180) / Math.PI;

	if (angleDeg <= thresholdDegrees) {
		return 'horizontal';
	}
	if (angleDeg >= 90 - thresholdDegrees) {
		return 'vertical';
	}
	return 'diagonal';
}

/**
 * Formats an elapsed duration in seconds into single-unit human readable form:
 * `Xd` (days), `Xh` (hours), or `Xm` (minutes).
 */
export function formatElapsedTime(seconds: number): string {
	const sec = Math.abs(seconds);
	if (!Number.isFinite(sec)) return '0m';
	if (sec >= 86400) {
		const days = Math.round(sec / 86400);
		return `${days}d`;
	}
	if (sec >= 3600) {
		const hours = Math.round(sec / 3600);
		return `${hours}h`;
	}
	const minutes = Math.round(sec / 60);
	return `${minutes}m`;
}

/**
 * Formats a bar count into e.g. `'1 bar'` or `'12 bars'`.
 */
export function formatBarsCount(bars: number): string {
	const count = Math.round(Math.abs(bars));
	return count === 1 ? '1 bar' : `${count} bars`;
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
 * e.g. `"+2.31 (+4.6%)"` for a rise and `"-2.31 (-4.6%)"`.
 * When metrics are supplied, appends ` · {bars} bars, {elapsed}`.
 */
export function formatMeasureLabel(
	delta: number,
	percent: number,
	metrics?: MeasureMetrics
): string {
	const base = `${formatSigned(delta, 2)} (${formatSigned(percent, 1)}%)`;
	if (!metrics) return base;

	const parts: string[] = [];
	if (metrics.bars !== undefined) {
		parts.push(formatBarsCount(metrics.bars));
	}
	if (metrics.elapsed !== undefined) {
		parts.push(metrics.elapsed);
	} else if (metrics.elapsedSeconds !== undefined) {
		parts.push(formatElapsedTime(metrics.elapsedSeconds));
	}

	if (parts.length === 0) return base;
	return `${base} · ${parts.join(', ')}`;
}

/** Convenience wrapper computing and formatting in one call. */
export function formatMeasureLabelForPoints(
	p1: DrawingPoint,
	p2: DrawingPoint,
	metrics?: MeasureMetrics
): string {
	const { delta, percent } = computeMeasure(p1, p2);
	return formatMeasureLabel(delta, percent, metrics);
}
