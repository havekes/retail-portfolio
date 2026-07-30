import { describe, it, expect } from 'vitest';
import { blendedAverageCost } from './average-cost';

describe('blendedAverageCost', () => {
	it('returns 0 for empty array', () => {
		expect(blendedAverageCost([])).toBe(0);
	});

	it('returns the average_cost for a single holding', () => {
		expect(blendedAverageCost([{ quantity: 10, average_cost: 50 }])).toBe(50);
	});

	it('computes quantity-weighted blend across multiple holdings', () => {
		const holdings = [
			{ quantity: 10, average_cost: 100 },
			{ quantity: 20, average_cost: 200 }
		];
		// (10*100 + 20*200) / (10 + 20) = 5000 / 30 = 166.666...
		expect(blendedAverageCost(holdings)).toBeCloseTo(166.6667);
	});

	it('ignores zero-quantity holdings in the blend', () => {
		const holdings = [
			{ quantity: 10, average_cost: 100 },
			{ quantity: 0, average_cost: 999 }
		];
		expect(blendedAverageCost(holdings)).toBe(100);
	});

	it('returns 0 when all quantities are zero', () => {
		const holdings = [
			{ quantity: 0, average_cost: 100 },
			{ quantity: 0, average_cost: 200 }
		];
		expect(blendedAverageCost(holdings)).toBe(0);
	});

	it('treats undefined average_cost as 0', () => {
		const holdings: { quantity: number; average_cost?: number }[] = [
			{ quantity: 10, average_cost: 100 },
			{ quantity: 10, average_cost: undefined }
		];
		// (10*100 + 10*0) / 20 = 50
		expect(blendedAverageCost(holdings)).toBe(50);
	});
});
