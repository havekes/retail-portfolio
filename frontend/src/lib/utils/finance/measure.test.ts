import { describe, it, expect } from 'vitest';
import type { Time } from 'lightweight-charts';
import {
	computeMeasure,
	formatMeasureLabel,
	formatMeasureLabelForPoints,
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
});

describe('formatMeasureLabelForPoints', () => {
	it('computes and formats the label from two anchors', () => {
		expect(formatMeasureLabelForPoints(p(100), p(102.31))).toBe('+2.31 (+2.3%)');
	});
});
