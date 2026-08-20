import { describe, it, expect } from 'vitest';
import {
	getWaveTargetPrice,
	calculateUpsidePercentage,
	updateSecurityElliottWaves,
	getSecurityDegreeWaveCount,
	type DegreeWaveCount,
	type SecurityElliottWaves,
	type WaveDegree
} from './elliott-wave';

describe('elliott-wave finance utilities', () => {
	const sampleWaveCount: DegreeWaveCount = {
		points: [
			{ wave: 1, time: '2024-01-01', price: 100 },
			{ wave: 2, time: '2024-01-02', price: 80 },
			{ wave: 3, time: '2024-01-03', price: 150 },
			{ wave: 4, time: '2024-01-04', price: 120 },
			{ wave: 5, time: '2024-01-05', price: 200 }
		]
	};

	describe('getWaveTargetPrice', () => {
		it('returns null if waveCount is null or undefined', () => {
			expect(getWaveTargetPrice(null, 'wave3')).toBeNull();
			expect(getWaveTargetPrice(undefined, 'wave5')).toBeNull();
		});

		it('extracts wave 3 peak price from points when no override is set', () => {
			expect(getWaveTargetPrice(sampleWaveCount, 'wave3')).toBe(150);
		});

		it('extracts wave 5 peak price from points when no override is set', () => {
			expect(getWaveTargetPrice(sampleWaveCount, 'wave5')).toBe(200);
		});

		it('prefers explicit wave3Target override over points', () => {
			const countWithOverride: DegreeWaveCount = {
				...sampleWaveCount,
				wave3Target: 175
			};
			expect(getWaveTargetPrice(countWithOverride, 'wave3')).toBe(175);
		});

		it('prefers explicit wave5Target override over points', () => {
			const countWithOverride: DegreeWaveCount = {
				...sampleWaveCount,
				wave5Target: 250
			};
			expect(getWaveTargetPrice(countWithOverride, 'wave5')).toBe(250);
		});

		it('respects 0 as a valid target override', () => {
			const countWithZeroOverride: DegreeWaveCount = {
				...sampleWaveCount,
				wave3Target: 0,
				wave5Target: 0
			};
			expect(getWaveTargetPrice(countWithZeroOverride, 'wave3')).toBe(0);
			expect(getWaveTargetPrice(countWithZeroOverride, 'wave5')).toBe(0);
		});

		it('falls back to points if target override is null or undefined', () => {
			const countWithNullOverride: DegreeWaveCount = {
				...sampleWaveCount,
				wave3Target: null,
				wave5Target: undefined
			};
			expect(getWaveTargetPrice(countWithNullOverride, 'wave3')).toBe(150);
			expect(getWaveTargetPrice(countWithNullOverride, 'wave5')).toBe(200);
		});

		it('returns null if points array does not contain target wave point and no override exists', () => {
			const partialCount: DegreeWaveCount = {
				points: [
					{ wave: 1, time: '2024-01-01', price: 100 },
					{ wave: 2, time: '2024-01-02', price: 80 }
				]
			};
			expect(getWaveTargetPrice(partialCount, 'wave3')).toBeNull();
			expect(getWaveTargetPrice(partialCount, 'wave5')).toBeNull();
		});

		it('returns null if points array is empty', () => {
			const emptyCount: DegreeWaveCount = { points: [] };
			expect(getWaveTargetPrice(emptyCount, 'wave3')).toBeNull();
			expect(getWaveTargetPrice(emptyCount, 'wave5')).toBeNull();
		});

		it('returns null if target wave point has invalid price', () => {
			const invalidPriceCount: DegreeWaveCount = {
				points: [{ wave: 3, time: '2024-01-01', price: NaN }]
			};
			expect(getWaveTargetPrice(invalidPriceCount, 'wave3')).toBeNull();
		});

		it('returns null if unknown targetWave passed at runtime', () => {
			// @ts-expect-error test invalid target wave
			expect(getWaveTargetPrice(sampleWaveCount, 'waveX')).toBeNull();
		});
	});

	describe('calculateUpsidePercentage', () => {
		it('calculates positive upside percentage correctly', () => {
			// ((150 - 100) / 100) * 100 = 50%
			expect(calculateUpsidePercentage(150, 100)).toBe(50);
		});

		it('calculates negative downside percentage correctly', () => {
			// ((80 - 100) / 100) * 100 = -20%
			expect(calculateUpsidePercentage(80, 100)).toBe(-20);
		});

		it('returns 0% when targetPrice equals currentPrice', () => {
			expect(calculateUpsidePercentage(100, 100)).toBe(0);
		});

		it('handles decimal precision correctly', () => {
			// ((250 - 180) / 180) * 100 = 38.88888888888889%
			expect(calculateUpsidePercentage(250, 180)).toBeCloseTo(38.88888888888889);
		});

		it('returns null if currentPrice is 0 (avoid division by zero)', () => {
			expect(calculateUpsidePercentage(100, 0)).toBeNull();
		});

		it('returns null if currentPrice is negative', () => {
			expect(calculateUpsidePercentage(100, -50)).toBeNull();
		});

		it('returns null if targetPrice is nullish or non-numeric', () => {
			expect(calculateUpsidePercentage(null, 100)).toBeNull();
			expect(calculateUpsidePercentage(undefined, 100)).toBeNull();
			expect(calculateUpsidePercentage(NaN, 100)).toBeNull();
			expect(calculateUpsidePercentage(Infinity, 100)).toBeNull();
		});

		it('returns null if currentPrice is nullish or non-numeric', () => {
			expect(calculateUpsidePercentage(150, null)).toBeNull();
			expect(calculateUpsidePercentage(150, undefined)).toBeNull();
			expect(calculateUpsidePercentage(150, NaN)).toBeNull();
			expect(calculateUpsidePercentage(150, Infinity)).toBeNull();
		});
	});

	describe('updateSecurityElliottWaves', () => {
		it('creates new preferences mapping when existingWaves is null or undefined', () => {
			const result = updateSecurityElliottWaves(null, 'sec-1', 'cycle', sampleWaveCount);
			expect(result).toEqual({
				'sec-1': {
					cycle: sampleWaveCount
				}
			});
		});

		it('updates degree wave count while preserving other degrees and securities', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					cycle: sampleWaveCount,
					primary: null
				},
				'sec-2': {
					primary: sampleWaveCount
				}
			};

			const primaryCount: DegreeWaveCount = {
				points: [{ wave: 1, time: '2024-02-01', price: 50 }]
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', 'primary', primaryCount);

			expect(updated['sec-1'].cycle).toEqual(sampleWaveCount);
			expect(updated['sec-1'].primary).toEqual(primaryCount);
			expect(updated['sec-2'].primary).toEqual(sampleWaveCount);
		});

		it('returns a new object without mutating the original input', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					cycle: sampleWaveCount
				}
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', 'primary', null);

			expect(updated).not.toBe(initial);
			expect(updated['sec-1']).not.toBe(initial['sec-1']);
			expect(initial['sec-1'].primary).toBeUndefined();
			expect(updated['sec-1'].primary).toBeNull();
		});

		it('allows clearing a degree count by passing null', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					cycle: sampleWaveCount
				}
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', 'cycle', null);
			expect(updated['sec-1'].cycle).toBeNull();
		});
	});

	describe('getSecurityDegreeWaveCount', () => {
		it('returns null if existingWaves is null or undefined', () => {
			expect(getSecurityDegreeWaveCount(null, 'sec-1', 'cycle')).toBeNull();
			expect(getSecurityDegreeWaveCount(undefined, 'sec-1', 'cycle')).toBeNull();
		});

		it('returns null if securityId or degree is falsy', () => {
			expect(
				getSecurityDegreeWaveCount({ 'sec-1': { cycle: sampleWaveCount } }, '', 'cycle')
			).toBeNull();
			expect(
				getSecurityDegreeWaveCount(
					{ 'sec-1': { cycle: sampleWaveCount } },
					'sec-1',
					'' as unknown as WaveDegree
				)
			).toBeNull();
		});

		it('returns null if security is not in existingWaves', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { cycle: sampleWaveCount }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-2', 'cycle')).toBeNull();
		});

		it('returns null if degree is null or undefined for the security', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { cycle: sampleWaveCount, primary: null }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-1', 'primary')).toBeNull();
		});

		it('returns the wave count when present', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { cycle: sampleWaveCount }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-1', 'cycle')).toEqual(sampleWaveCount);
		});
	});
});
