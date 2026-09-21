import { describe, it, expect } from 'vitest';
import { pointToSegmentDistance } from './geometry';

describe('pointToSegmentDistance', () => {
	it('calculates perpendicular distance for point projecting onto the interior', () => {
		// Horizontal segment from (0, 0) to (10, 0)
		const dist = pointToSegmentDistance(5, 4, 0, 0, 10, 0);
		expect(dist).toBeCloseTo(4);
	});

	it('clamps to p1 when projection falls before the start of the segment', () => {
		// Point (-3, 4) relative to p1(0, 0) -> distance = hypot(-3, 4) = 5
		const dist = pointToSegmentDistance(-3, 4, 0, 0, 10, 0);
		expect(dist).toBeCloseTo(5);
	});

	it('clamps to p2 when projection falls beyond the end of the segment', () => {
		// Point (13, 4) relative to p2(10, 0) -> distance = hypot(3, 4) = 5
		const dist = pointToSegmentDistance(13, 4, 0, 0, 10, 0);
		expect(dist).toBeCloseTo(5);
	});

	it('returns 0 for points exactly on the segment', () => {
		expect(pointToSegmentDistance(5, 0, 0, 0, 10, 0)).toBeCloseTo(0);
		expect(pointToSegmentDistance(0, 0, 0, 0, 10, 0)).toBeCloseTo(0);
		expect(pointToSegmentDistance(10, 0, 0, 0, 10, 0)).toBeCloseTo(0);
	});

	it('handles zero-length (degenerate) segments by computing distance to the single point', () => {
		// p1 and p2 are both at (5, 5)
		const dist = pointToSegmentDistance(8, 9, 5, 5, 5, 5);
		// dx = 3, dy = 4 -> hypot = 5
		expect(dist).toBeCloseTo(5);
	});

	it('handles diagonal segments accurately', () => {
		// Segment from (0, 0) to (10, 10)
		// Midpoint is (5, 5). Point (2, 8) has projection at (5, 5)
		// Vector from (5, 5) to (2, 8) is (-3, 3) -> hypot = sqrt(18) ≈ 4.2426
		const dist = pointToSegmentDistance(2, 8, 0, 0, 10, 10);
		expect(dist).toBeCloseTo(Math.hypot(-3, 3));
	});

	it('clamps collinear points extending beyond endpoints', () => {
		// Horizontal segment from (0, 0) to (10, 0)
		// Point at (-5, 0) -> clamped to p1 -> distance = 5
		expect(pointToSegmentDistance(-5, 0, 0, 0, 10, 0)).toBeCloseTo(5);
		// Point at (15, 0) -> clamped to p2 -> distance = 5
		expect(pointToSegmentDistance(15, 0, 0, 0, 10, 0)).toBeCloseTo(5);
	});
});
