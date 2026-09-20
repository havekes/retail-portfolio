import { describe, it, expect } from 'vitest';
import type { Time } from 'lightweight-charts';
import {
	computeMeasure,
	formatMeasureLabel,
	formatMeasureLabelForPoints,
	snapMeasureAngle,
	formatElapsedTime,
	formatBarsCount,
	type MeasureComputation
} from './measure';
import type { DrawingPoint } from './drawings';

const p = (price: number, time: string = '2024-01-01'): DrawingPoint => ({
	time: time as Time,
	price
});

describe('computeMeasure', () => {
	it('reports an up move with positive delta and percent', () => {
		const result = computeMeasure(p(100), p(102.31));
		expect(result.delta).toBeCloseTo(2.31);
		expect(result.percent).toBeCloseTo(2.31);
		expect(result.direction).toBe('up');
	});

	it('reports a down move with negative delta and percent', () => {
		const result = computeMeasure(p(104.6), p(100));
		expect(result.delta).toBeCloseTo(-4.6);
		expect(result.percent).toBeCloseTo((-4.6 / 104.6) * 100);
		expect(result.direction).toBe('down');
	});

	it('reports a flat move when prices are identical', () => {
		const result = computeMeasure(p(123.45), p(123.45));
		expect(result.delta).toBe(0);
		expect(result.percent).toBe(0);
		expect(result.direction).toBe('flat');
	});

	it('keeps direction but zeroes percent when the first price is zero (div-by-zero guard)', () => {
		const result = computeMeasure(p(0), p(5));
		expect(result.delta).toBe(5);
		expect(result.percent).toBe(0);
		expect(result.direction).toBe('up');
	});

	it('is order-sensitive: swapping anchors flips direction and delta', () => {
		const up = computeMeasure(p(100), p(150));
		const down = computeMeasure(p(150), p(100));
		expect(up.direction).toBe('up');
		expect(down.direction).toBe('down');
		expect(up.delta).toBe(-down.delta);
	});

	it('handles fractional prices with float precision', () => {
		const result: MeasureComputation = computeMeasure(p(0.1), p(0.3));
		expect(result.delta).toBeCloseTo(0.2, 10);
		expect(result.percent).toBeCloseTo(200, 10);
	});
});

describe('formatMeasureLabel', () => {
	it('formats a rise with explicit plus signs for delta and percent', () => {
		expect(formatMeasureLabel(2.31, 4.6)).toBe('+2.31 (+4.6%)');
	});

	it('formats a fall with minus signs already present', () => {
		expect(formatMeasureLabel(-2.31, -4.6)).toBe('-2.31 (-4.6%)');
	});

	it('formats a flat move without signs', () => {
		expect(formatMeasureLabel(0, 0)).toBe('0.00 (0.0%)');
	});

	it('rounds to two decimals for the delta and one decimal for the percent', () => {
		expect(formatMeasureLabel(1.005, 0.4849)).toBe('+1.00 (+0.5%)');
	});

	it('normalizes values that round to zero to an unsigned zero', () => {
		expect(formatMeasureLabel(-0.001, -0.04)).toBe('0.00 (0.0%)');
	});

	it('falls back to zero for non-finite input', () => {
		expect(formatMeasureLabel(NaN, Infinity)).toBe('0.00 (0.0%)');
	});

	it('formats label with bars and elapsed time when metrics are supplied', () => {
		expect(formatMeasureLabel(2.5, 5.0, { bars: 12, elapsed: '12d' })).toBe(
			'+2.50 (+5.0%) · 12 bars, 12d'
		);
		expect(formatMeasureLabel(2.5, 5.0, { bars: 1, elapsedSeconds: 3600 })).toBe(
			'+2.50 (+5.0%) · 1 bar, 1h'
		);
		expect(formatMeasureLabel(2.5, 5.0, { bars: 12, elapsedSeconds: 12 * 86400 })).toBe(
			'+2.50 (+5.0%) · 12 bars, 12d'
		);
	});

	it('formats label with only bars or only elapsed duration if one is omitted', () => {
		expect(formatMeasureLabel(1.23, 2.4, { bars: 5 })).toBe('+1.23 (+2.4%) · 5 bars');
		expect(formatMeasureLabel(1.23, 2.4, { elapsedSeconds: 120 })).toBe('+1.23 (+2.4%) · 2m');
	});
});

describe('formatMeasureLabelForPoints', () => {
	it('computes and formats the label from two anchors', () => {
		expect(formatMeasureLabelForPoints(p(100), p(102.31))).toBe('+2.31 (+2.3%)');
	});

	it('includes metrics when passed to formatMeasureLabelForPoints', () => {
		expect(formatMeasureLabelForPoints(p(100), p(105), { bars: 12, elapsed: '12d' })).toBe(
			'+5.00 (+5.0%) · 12 bars, 12d'
		);
	});
});

describe('snapMeasureAngle', () => {
	it('snaps dominant horizontal movement to "horizontal"', () => {
		// ~5.7 degrees
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 100, y: 10 })).toBe('horizontal');
		// exactly 0 degrees
		expect(snapMeasureAngle({ x: 0, y: 50 }, { x: 200, y: 50 })).toBe('horizontal');
		// negative dx/dy within threshold
		expect(snapMeasureAngle({ x: 100, y: 50 }, { x: 0, y: 40 })).toBe('horizontal');
	});

	it('snaps dominant vertical movement to "vertical"', () => {
		// ~84.3 degrees
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 10, y: 100 })).toBe('vertical');
		// exactly 90 degrees
		expect(snapMeasureAngle({ x: 50, y: 0 }, { x: 50, y: 200 })).toBe('vertical');
		// negative dy
		expect(snapMeasureAngle({ x: 50, y: 200 }, { x: 45, y: 0 })).toBe('vertical');
	});

	it('preserves diagonal movement when angle is balanced', () => {
		// 45 degrees
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 50, y: 50 })).toBe('diagonal');
		// 30 degrees
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 100, y: 57.7 })).toBe('diagonal');
		// 60 degrees
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 57.7, y: 100 })).toBe('diagonal');
	});

	it('defaults to diagonal when points are identical', () => {
		expect(snapMeasureAngle({ x: 10, y: 10 }, { x: 10, y: 10 })).toBe('diagonal');
	});

	it('respects custom threshold degrees', () => {
		// 20 degrees: diagonal with threshold 15, horizontal with threshold 25
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 100, y: 36.4 }, 15)).toBe('diagonal');
		expect(snapMeasureAngle({ x: 0, y: 0 }, { x: 100, y: 36.4 }, 25)).toBe('horizontal');
	});
});

describe('formatElapsedTime', () => {
	it('formats days for spans of 1 day or more', () => {
		expect(formatElapsedTime(86400)).toBe('1d');
		expect(formatElapsedTime(12 * 86400)).toBe('12d');
		expect(formatElapsedTime(2.5 * 86400)).toBe('3d');
	});

	it('formats hours for spans between 1 hour and 1 day', () => {
		expect(formatElapsedTime(3600)).toBe('1h');
		expect(formatElapsedTime(4 * 3600)).toBe('4h');
		expect(formatElapsedTime(23 * 3600)).toBe('23h');
	});

	it('formats minutes for spans under 1 hour', () => {
		expect(formatElapsedTime(60)).toBe('1m');
		expect(formatElapsedTime(45 * 60)).toBe('45m');
		expect(formatElapsedTime(0)).toBe('0m');
	});

	it('handles negative durations by absolute value', () => {
		expect(formatElapsedTime(-86400)).toBe('1d');
		expect(formatElapsedTime(-3600)).toBe('1h');
	});
});

describe('formatBarsCount', () => {
	it('formats singular bar for 1', () => {
		expect(formatBarsCount(1)).toBe('1 bar');
		expect(formatBarsCount(-1)).toBe('1 bar');
	});

	it('formats plural bars for other counts', () => {
		expect(formatBarsCount(0)).toBe('0 bars');
		expect(formatBarsCount(12)).toBe('12 bars');
		expect(formatBarsCount(-12)).toBe('12 bars');
	});
});
