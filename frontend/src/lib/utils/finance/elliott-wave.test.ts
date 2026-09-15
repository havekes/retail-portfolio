import { describe, it, expect } from 'vitest';
import {
	getWaveTargetPrice,
	calculateUpsidePercentage,
	updateSecurityElliottWaves,
	getSecurityDegreeWaveCount,
	selectDegreeWave,
	getWaveIdentity,
	normalizeWaveIds,
	areWaveCountsEqual,
	areSecurityElliottWavesEqual,
	getWaveAlertPercent,
	areWaveSettingsEqual,
	DEFAULT_WAVE_SETTINGS,
	type DegreeWaveCount,
	type SecurityElliottWaves,
	type WaveDegree,
	type WaveSettings
} from './elliott-wave';

describe('elliott-wave finance utilities', () => {
	const sampleWaveCount: DegreeWaveCount = {
		id: 'w-sample',
		degree: 'cycle',
		type: 'impulse',
		points: [
			{ wave: 0, time: '2024-01-01', price: 50 },
			{ wave: 1, time: '2024-01-02', price: 100 },
			{ wave: 2, time: '2024-01-03', price: 80 },
			{ wave: 3, time: '2024-01-04', price: 150 },
			{ wave: 4, time: '2024-01-05', price: 120 },
			{ wave: 5, time: '2024-01-06', price: 200 }
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
				id: 'w-partial',
				degree: 'cycle',
				type: 'impulse',
				points: [
					{ wave: 1, time: '2024-01-01', price: 100 },
					{ wave: 2, time: '2024-01-02', price: 80 }
				]
			};
			expect(getWaveTargetPrice(partialCount, 'wave3')).toBeNull();
			expect(getWaveTargetPrice(partialCount, 'wave5')).toBeNull();
		});

		it('returns null if points array is empty', () => {
			const emptyCount: DegreeWaveCount = {
				id: 'w-empty',
				degree: 'cycle',
				type: 'impulse',
				points: []
			};
			expect(getWaveTargetPrice(emptyCount, 'wave3')).toBeNull();
			expect(getWaveTargetPrice(emptyCount, 'wave5')).toBeNull();
		});

		it('returns null if target wave point has invalid price', () => {
			const invalidPriceCount: DegreeWaveCount = {
				id: 'w-invalid-price',
				degree: 'cycle',
				type: 'impulse',
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
			const result = updateSecurityElliottWaves(null, 'sec-1', [sampleWaveCount]);
			expect(result).toEqual({
				'sec-1': {
					waves: [sampleWaveCount]
				}
			});
		});

		it('updates wave counts while preserving other securities', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					waves: [sampleWaveCount]
				},
				'sec-2': {
					waves: [sampleWaveCount]
				}
			};

			const primaryCount: DegreeWaveCount = {
				id: 'w-primary',
				degree: 'primary',
				type: 'impulse',
				points: [{ wave: 1, time: '2024-02-01', price: 50 }]
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', [primaryCount]);

			expect(updated['sec-1'].waves).toEqual([primaryCount]);
			expect(updated['sec-2'].waves).toEqual([sampleWaveCount]);
		});

		it('returns a new object without mutating the original input', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					waves: [sampleWaveCount]
				}
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', []);

			expect(updated).not.toBe(initial);
			expect(updated['sec-1']).not.toBe(initial['sec-1']);
			expect(initial['sec-1'].waves).toEqual([sampleWaveCount]);
			expect(updated['sec-1'].waves).toEqual([]);
		});

		it('allows clearing waves by passing empty array', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					waves: [sampleWaveCount]
				}
			};

			const updated = updateSecurityElliottWaves(initial, 'sec-1', []);
			expect(updated['sec-1'].waves).toEqual([]);
		});

		it('updates security with a multi-wave collection', () => {
			const initial: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					waves: [sampleWaveCount]
				}
			};

			const newWaves: DegreeWaveCount[] = [
				{
					id: 'w1',
					degree: 'cycle',
					type: 'impulse',
					points: [{ wave: 0, time: '2024-01-01', price: 10 }]
				},
				{
					id: 'w2',
					degree: 'primary',
					type: 'corrective',
					points: [{ wave: 0, time: '2024-01-05', price: 20 }]
				}
			];

			const updated = updateSecurityElliottWaves(initial, 'sec-1', newWaves);
			expect(updated['sec-1'].waves).toEqual(newWaves);
		});

		it('updates security using a DegreeWaveCount[] array payload', () => {
			const waveList: DegreeWaveCount[] = [
				{
					id: 'w1',
					degree: 'cycle',
					type: 'impulse',
					points: [{ wave: 0, time: '2024-01-01', price: 10 }]
				}
			];

			const updated = updateSecurityElliottWaves(null, 'sec-1', waveList);
			expect(updated['sec-1'].waves).toEqual(waveList);
		});
	});

	describe('getSecurityDegreeWaveCount', () => {
		it('extracts degree count when present in waves array', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': {
					waves: [sampleWaveCount]
				}
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-1', 'cycle')).toEqual(sampleWaveCount);
		});

		it('returns null if existingWaves is null or undefined', () => {
			expect(getSecurityDegreeWaveCount(null, 'sec-1', 'cycle')).toBeNull();
			expect(getSecurityDegreeWaveCount(undefined, 'sec-1', 'cycle')).toBeNull();
		});

		it('returns null if securityId or degree is falsy', () => {
			expect(
				getSecurityDegreeWaveCount({ 'sec-1': { waves: [sampleWaveCount] } }, '', 'cycle')
			).toBeNull();
			expect(
				getSecurityDegreeWaveCount(
					{ 'sec-1': { waves: [sampleWaveCount] } },
					'sec-1',
					'' as unknown as WaveDegree
				)
			).toBeNull();
		});

		it('returns null if security is not in existingWaves', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { waves: [sampleWaveCount] }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-2', 'cycle')).toBeNull();
		});

		it('returns null if degree is not in the waves array', () => {
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { waves: [sampleWaveCount] }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-1', 'primary')).toBeNull();
		});

		it('prefers impulse wave when multiple waves of same degree exist', () => {
			const corrective: DegreeWaveCount = {
				id: 'c1',
				degree: 'cycle',
				type: 'corrective',
				points: [{ wave: 'A', time: '2024-01-01', price: 10 }]
			};
			const impulse: DegreeWaveCount = {
				id: 'i1',
				degree: 'cycle',
				type: 'impulse',
				points: [{ wave: 1, time: '2024-01-02', price: 20 }]
			};
			const waves: Record<string, SecurityElliottWaves> = {
				'sec-1': { waves: [corrective, impulse] }
			};
			expect(getSecurityDegreeWaveCount(waves, 'sec-1', 'cycle')).toEqual(impulse);
		});
	});

	describe('areWaveCountsEqual', () => {
		it('returns true when both are null or undefined', () => {
			expect(areWaveCountsEqual(null, null)).toBe(true);
			expect(areWaveCountsEqual(undefined, undefined)).toBe(true);
			expect(areWaveCountsEqual(null, undefined)).toBe(true);
		});

		it('returns false when one is null and the other is not', () => {
			expect(areWaveCountsEqual(sampleWaveCount, null)).toBe(false);
			expect(areWaveCountsEqual(null, sampleWaveCount)).toBe(false);
		});

		it('returns true for identical wave counts', () => {
			const duplicate: DegreeWaveCount = {
				id: 'w-sample',
				degree: 'cycle',
				type: 'impulse',
				points: [
					{ wave: 0, time: '2024-01-01', price: 50 },
					{ wave: 1, time: '2024-01-02', price: 100 },
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			};
			expect(areWaveCountsEqual(sampleWaveCount, duplicate)).toBe(true);
		});

		it('returns false if point lengths differ', () => {
			const partial: DegreeWaveCount = {
				id: 'w-sample',
				degree: 'cycle',
				type: 'impulse',
				points: [{ wave: 0, time: '2024-01-01', price: 50 }]
			};
			expect(areWaveCountsEqual(sampleWaveCount, partial)).toBe(false);
		});

		it('returns false if point values differ', () => {
			const modified: DegreeWaveCount = {
				id: 'w-sample',
				degree: 'cycle',
				type: 'impulse',
				points: [
					{ wave: 0, time: '2024-01-01', price: 50 },
					{ wave: 1, time: '2024-01-02', price: 105 }, // different price
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			};
			expect(areWaveCountsEqual(sampleWaveCount, modified)).toBe(false);
		});

		it('returns false if point 0 differs', () => {
			const modifiedPoint0: DegreeWaveCount = {
				id: 'w-sample',
				degree: 'cycle',
				type: 'impulse',
				points: [
					{ wave: 0, time: '2024-01-01', price: 55 }, // different point 0 price
					{ wave: 1, time: '2024-01-02', price: 100 },
					{ wave: 2, time: '2024-01-03', price: 80 },
					{ wave: 3, time: '2024-01-04', price: 150 },
					{ wave: 4, time: '2024-01-05', price: 120 },
					{ wave: 5, time: '2024-01-06', price: 200 }
				]
			};
			expect(areWaveCountsEqual(sampleWaveCount, modifiedPoint0)).toBe(false);
		});

		it('returns false if wave target overrides differ', () => {
			const target1: DegreeWaveCount = { ...sampleWaveCount, wave3Target: 175 };
			const target2: DegreeWaveCount = { ...sampleWaveCount, wave3Target: 180 };
			expect(areWaveCountsEqual(target1, target2)).toBe(false);
		});

		it('returns true for identical corrective wave counts with letters A, B, C', () => {
			const corrective1: DegreeWaveCount = {
				id: 'c1',
				degree: 'cycle',
				type: 'corrective',
				points: [
					{ wave: 0, time: '2024-01-01', price: 100 },
					{ wave: 'A', time: '2024-01-02', price: 70 },
					{ wave: 'B', time: '2024-01-03', price: 85 },
					{ wave: 'C', time: '2024-01-04', price: 60 }
				]
			};
			const corrective2: DegreeWaveCount = {
				id: 'c1',
				degree: 'cycle',
				type: 'corrective',
				points: [
					{ wave: 0, time: '2024-01-01', price: 100 },
					{ wave: 'A', time: '2024-01-02', price: 70 },
					{ wave: 'B', time: '2024-01-03', price: 85 },
					{ wave: 'C', time: '2024-01-04', price: 60 }
				]
			};
			expect(areWaveCountsEqual(corrective1, corrective2)).toBe(true);
		});

		it('returns false when wave count types differ (impulse vs corrective)', () => {
			const impulse: DegreeWaveCount = {
				id: 'w1',
				degree: 'cycle',
				type: 'impulse',
				points: [{ wave: 0, time: '2024-01-01', price: 100 }]
			};
			const corrective: DegreeWaveCount = {
				id: 'w1',
				degree: 'cycle',
				type: 'corrective',
				points: [{ wave: 0, time: '2024-01-01', price: 100 }]
			};
			expect(areWaveCountsEqual(impulse, corrective)).toBe(false);
		});

		it('returns false when wave id differs', () => {
			const a: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			const b: DegreeWaveCount = { id: 'wave-2', degree: 'cycle', type: 'impulse', points: [] };
			expect(areWaveCountsEqual(a, b)).toBe(false);
		});

		it('returns true when wave id matches', () => {
			const a: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			const b: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			expect(areWaveCountsEqual(a, b)).toBe(true);
		});

		it('returns false when wave degree differs', () => {
			const a: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			const b: DegreeWaveCount = { id: 'wave-1', degree: 'primary', type: 'impulse', points: [] };
			expect(areWaveCountsEqual(a, b)).toBe(false);
		});

		it('returns true when wave degree matches', () => {
			const a: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			const b: DegreeWaveCount = { id: 'wave-1', degree: 'cycle', type: 'impulse', points: [] };
			expect(areWaveCountsEqual(a, b)).toBe(true);
		});
	});

	describe('selectDegreeWave', () => {
		const impulse: DegreeWaveCount = {
			id: 'i1',
			degree: 'cycle',
			type: 'impulse',
			points: [{ wave: 1, time: '2024-01-02', price: 20 }]
		};
		const laterImpulse: DegreeWaveCount = {
			id: 'i2',
			degree: 'cycle',
			type: 'impulse',
			points: [{ wave: 1, time: '2024-02-01', price: 30 }]
		};
		const corrective: DegreeWaveCount = {
			id: 'c1',
			degree: 'cycle',
			type: 'corrective',
			points: [{ wave: 'A', time: '2024-01-01', price: 10 }]
		};
		const laterCorrective: DegreeWaveCount = {
			id: 'c2',
			degree: 'cycle',
			type: 'corrective',
			points: [{ wave: 'A', time: '2024-02-01', price: 15 }]
		};

		it('returns null for empty or missing collections', () => {
			expect(selectDegreeWave(null, 'cycle')).toBeNull();
			expect(selectDegreeWave(undefined, 'cycle')).toBeNull();
			expect(selectDegreeWave([], 'cycle')).toBeNull();
		});

		it('returns null when the degree is absent', () => {
			expect(selectDegreeWave([impulse], 'primary')).toBeNull();
		});

		it('prefers the impulse wave of the degree by default', () => {
			expect(selectDegreeWave([corrective, impulse], 'cycle')).toBe(impulse);
		});

		it('falls back to any wave of the degree when no impulse exists', () => {
			expect(selectDegreeWave([corrective], 'cycle')).toBe(corrective);
		});

		it('honors a custom preferred type', () => {
			expect(
				selectDegreeWave([impulse, corrective], 'cycle', { preferredType: 'corrective' })
			).toBe(corrective);
		});

		it("prefers the most recent match when prefer is 'last'", () => {
			expect(selectDegreeWave([impulse, laterImpulse], 'cycle', { prefer: 'last' })).toBe(
				laterImpulse
			);
			// Falls back to the last any-degree wave when the preferred type is absent.
			expect(
				selectDegreeWave([corrective, laterCorrective], 'cycle', {
					preferredType: 'impulse',
					prefer: 'last'
				})
			).toBe(laterCorrective);
		});
	});

	describe('getWaveIdentity / normalizeWaveIds', () => {
		const idlessWaves: DegreeWaveCount[] = [
			{
				id: '',
				degree: 'cycle',
				type: 'impulse',
				points: [
					{ wave: 0, time: '2024-01-01', price: 10 },
					{ wave: 1, time: '2024-01-02', price: 20 }
				]
			},
			{
				id: undefined as unknown as string,
				degree: 'primary',
				type: 'corrective',
				points: []
			}
		];

		it('keeps a persisted id', () => {
			expect(getWaveIdentity({ ...idlessWaves[0], id: 'persisted' })).toBe('persisted');
		});

		it('derives a stable id from content and position', () => {
			expect(getWaveIdentity(idlessWaves[0], 0)).toBe(getWaveIdentity({ ...idlessWaves[0] }, 0));
			expect(getWaveIdentity(idlessWaves[0], 0)).not.toBe(
				getWaveIdentity({ ...idlessWaves[0], degree: 'primary' }, 0)
			);
			expect(getWaveIdentity(idlessWaves[0], 0)).not.toBe(getWaveIdentity(idlessWaves[0], 1));
		});

		it('assigns stable, distinct ids to every id-less wave without mutating input', () => {
			const first = normalizeWaveIds(idlessWaves);
			const second = normalizeWaveIds(idlessWaves);
			expect(first.map((w) => w.id)).toEqual(second.map((w) => w.id));
			expect(first[0].id).toBeTruthy();
			expect(first[1].id).toBeTruthy();
			expect(first[0].id).not.toBe(first[1].id);
			expect(first[0]).not.toBe(idlessWaves[0]);
			expect(idlessWaves[0].id).toBe('');
		});

		it('returns an empty array for null or undefined', () => {
			expect(normalizeWaveIds(null)).toEqual([]);
			expect(normalizeWaveIds(undefined)).toEqual([]);
		});
	});

	describe('areSecurityElliottWavesEqual', () => {
		it('returns true when both are null or undefined', () => {
			expect(areSecurityElliottWavesEqual(null, null)).toBe(true);
			expect(areSecurityElliottWavesEqual(undefined, undefined)).toBe(true);
			expect(areSecurityElliottWavesEqual(null, undefined)).toBe(true);
		});

		it('compares multi-wave collections correctly', () => {
			const a: SecurityElliottWaves = {
				waves: [
					{
						id: 'w1',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-01', price: 10 }]
					},
					{
						id: 'w2',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-05', price: 20 }]
					}
				]
			};
			const b: SecurityElliottWaves = {
				waves: [
					{
						id: 'w1',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-01', price: 10 }]
					},
					{
						id: 'w2',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-05', price: 20 }]
					}
				]
			};
			expect(areSecurityElliottWavesEqual(a, b)).toBe(true);

			const c: SecurityElliottWaves = {
				waves: [
					{
						id: 'w1',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-01', price: 10 }]
					}
				]
			};
			expect(areSecurityElliottWavesEqual(a, c)).toBe(false);
		});

		it('does not report spurious inequality for id-less waves round-tripped through normalization', () => {
			const loaded: SecurityElliottWaves = {
				waves: [
					{
						id: '',
						degree: 'cycle',
						type: 'impulse',
						points: [{ wave: 0, time: '2024-01-01', price: 10 }]
					},
					{
						id: undefined as unknown as string,
						degree: 'primary',
						type: 'corrective',
						points: []
					}
				]
			};
			const serialized: SecurityElliottWaves = { waves: normalizeWaveIds(loaded.waves) };

			// load -> serialize -> compare: identity was preserved, so they are equal.
			expect(areSecurityElliottWavesEqual(serialized, loaded)).toBe(true);
			// And normalizing the serialized form again is idempotent.
			expect(normalizeWaveIds(serialized.waves).map((w) => w.id)).toEqual(
				serialized.waves.map((w) => w.id)
			);
		});

		it('still distinguishes different persisted wave ids', () => {
			const a: SecurityElliottWaves = {
				waves: [{ id: 'a', degree: 'cycle', type: 'impulse', points: [] }]
			};
			const b: SecurityElliottWaves = {
				waves: [{ id: 'b', degree: 'cycle', type: 'impulse', points: [] }]
			};
			expect(areSecurityElliottWavesEqual(a, b)).toBe(false);
		});
	});

	describe('DEFAULT_WAVE_SETTINGS', () => {
		it('has snap-to-wick off and all alert percents null', () => {
			expect(DEFAULT_WAVE_SETTINGS.snap_to_wicks).toBe(null);
			expect(DEFAULT_WAVE_SETTINGS.alert_percents).toEqual({
				cycle: { wave3: null, wave5: null },
				primary: { wave3: null, wave5: null },
				intermediate: { wave3: null, wave5: null }
			});
		});
	});

	describe('areWaveSettingsEqual', () => {
		const fullSettings: WaveSettings = {
			snap_to_wicks: true,
			alert_percents: {
				cycle: { wave3: 5, wave5: 10 },
				primary: { wave3: 15, wave5: 20 },
				intermediate: { wave3: 25, wave5: 30 }
			}
		};

		it('returns true when both are null or undefined', () => {
			expect(areWaveSettingsEqual(null, null)).toBe(true);
			expect(areWaveSettingsEqual(undefined, undefined)).toBe(true);
			expect(areWaveSettingsEqual(null, undefined)).toBe(true);
		});

		it('returns false when one is nullish and the other is not', () => {
			expect(areWaveSettingsEqual(fullSettings, null)).toBe(false);
			expect(areWaveSettingsEqual(undefined, fullSettings)).toBe(false);
		});

		it('returns true for identical nested settings', () => {
			expect(
				areWaveSettingsEqual(fullSettings, {
					snap_to_wicks: true,
					alert_percents: {
						cycle: { wave3: 5, wave5: 10 },
						primary: { wave3: 15, wave5: 20 },
						intermediate: { wave3: 25, wave5: 30 }
					}
				})
			).toBe(true);
		});

		it('returns false when snap_to_wicks differs', () => {
			const other = { ...fullSettings, snap_to_wicks: false };
			expect(areWaveSettingsEqual(fullSettings, other)).toBe(false);
		});

		it('returns false when each alert percent slot differs', () => {
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 6, wave5: 10 },
						primary: { wave3: 15, wave5: 20 },
						intermediate: { wave3: 25, wave5: 30 }
					}
				})
			).toBe(false);
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 5, wave5: 11 },
						primary: { wave3: 15, wave5: 20 },
						intermediate: { wave3: 25, wave5: 30 }
					}
				})
			).toBe(false);
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 5, wave5: 10 },
						primary: { wave3: 16, wave5: 20 },
						intermediate: { wave3: 25, wave5: 30 }
					}
				})
			).toBe(false);
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 5, wave5: 10 },
						primary: { wave3: 15, wave5: 21 },
						intermediate: { wave3: 25, wave5: 30 }
					}
				})
			).toBe(false);
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 5, wave5: 10 },
						primary: { wave3: 15, wave5: 20 },
						intermediate: { wave3: 26, wave5: 30 }
					}
				})
			).toBe(false);
			expect(
				areWaveSettingsEqual(fullSettings, {
					...fullSettings,
					alert_percents: {
						cycle: { wave3: 5, wave5: 10 },
						primary: { wave3: 15, wave5: 20 },
						intermediate: { wave3: 25, wave5: 31 }
					}
				})
			).toBe(false);
		});

		it('compares equal when a degree entry is missing instead of throwing', () => {
			const missingPrimaryDegree = {
				snap_to_wicks: null,
				alert_percents: { cycle: { wave3: 5, wave5: 10 } }
			} as unknown as WaveSettings;
			const nullShapedPrimary = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: 5, wave5: 10 },
					primary: { wave3: null, wave5: null },
					intermediate: { wave3: null, wave5: null }
				}
			} as WaveSettings;
			// A stored settings object missing the `primary` degree key (possible via the
			// permissive backend schema) must not throw and must compare equal to the
			// equivalent null-shaped settings (missing degree == all null for that degree).
			expect(() => areWaveSettingsEqual(missingPrimaryDegree, nullShapedPrimary)).not.toThrow();
			expect(areWaveSettingsEqual(missingPrimaryDegree, nullShapedPrimary)).toBe(true);
			expect(areWaveSettingsEqual(nullShapedPrimary, missingPrimaryDegree)).toBe(true);

			const missingCycleDegree = {
				snap_to_wicks: null,
				alert_percents: { primary: { wave3: 15, wave5: 20 } }
			} as unknown as WaveSettings;
			const nullShapedCycle = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: 15, wave5: 20 },
					intermediate: { wave3: null, wave5: null }
				}
			} as WaveSettings;
			expect(() => areWaveSettingsEqual(missingCycleDegree, nullShapedCycle)).not.toThrow();
			expect(areWaveSettingsEqual(missingCycleDegree, nullShapedCycle)).toBe(true);
			expect(areWaveSettingsEqual(nullShapedCycle, missingCycleDegree)).toBe(true);

			const missingIntermediateDegree = {
				snap_to_wicks: null,
				alert_percents: { cycle: { wave3: 5, wave5: 10 }, primary: { wave3: 15, wave5: 20 } }
			} as unknown as WaveSettings;
			const nullShapedIntermediate = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: 5, wave5: 10 },
					primary: { wave3: 15, wave5: 20 },
					intermediate: { wave3: null, wave5: null }
				}
			} as WaveSettings;
			expect(() =>
				areWaveSettingsEqual(missingIntermediateDegree, nullShapedIntermediate)
			).not.toThrow();
			expect(areWaveSettingsEqual(missingIntermediateDegree, nullShapedIntermediate)).toBe(true);
			expect(areWaveSettingsEqual(nullShapedIntermediate, missingIntermediateDegree)).toBe(true);
		});

		it('returns true when null and undefined field values both mean off', () => {
			const withNull: WaveSettings = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null },
					intermediate: { wave3: null, wave5: null }
				}
			};
			expect(
				areWaveSettingsEqual(
					{ snap_to_wicks: undefined, alert_percents: withNull.alert_percents },
					withNull
				)
			).toBe(true);
			expect(areWaveSettingsEqual({ snap_to_wicks: undefined }, {})).toBe(true);
			expect(areWaveSettingsEqual(DEFAULT_WAVE_SETTINGS, withNull)).toBe(true);
		});

		it('returns false when alert_percents is null vs populated', () => {
			expect(areWaveSettingsEqual({ snap_to_wicks: true }, fullSettings)).toBe(false);
		});
	});

	describe('getWaveAlertPercent', () => {
		const configured: WaveSettings = {
			snap_to_wicks: true,
			alert_percents: {
				cycle: { wave3: 5, wave5: 10 },
				primary: { wave3: 15, wave5: 20 },
				intermediate: { wave3: 25, wave5: 30 }
			}
		};

		it('returns the configured value for each degree+wave combination', () => {
			expect(getWaveAlertPercent(configured, 'cycle', 'wave3')).toBe(5);
			expect(getWaveAlertPercent(configured, 'cycle', 'wave5')).toBe(10);
			expect(getWaveAlertPercent(configured, 'primary', 'wave3')).toBe(15);
			expect(getWaveAlertPercent(configured, 'primary', 'wave5')).toBe(20);
			expect(getWaveAlertPercent(configured, 'intermediate', 'wave3')).toBe(25);
			expect(getWaveAlertPercent(configured, 'intermediate', 'wave5')).toBe(30);
		});

		it('returns null for nullish settings', () => {
			expect(getWaveAlertPercent(null, 'cycle', 'wave3')).toBe(null);
			expect(getWaveAlertPercent(undefined, 'primary', 'wave5')).toBe(null);
			expect(getWaveAlertPercent(null, 'intermediate', 'wave3')).toBe(null);
		});

		it('returns null when alert_percents is null or missing', () => {
			expect(getWaveAlertPercent({ snap_to_wicks: true }, 'cycle', 'wave3')).toBe(null);
			expect(
				getWaveAlertPercent({ snap_to_wicks: true, alert_percents: null }, 'cycle', 'wave3')
			).toBe(null);
		});

		it('returns null when a degree entry or wave slot is missing', () => {
			const missingDegree = {
				snap_to_wicks: null,
				alert_percents: { cycle: { wave3: 5, wave5: null } }
			} as unknown as WaveSettings;
			expect(getWaveAlertPercent(missingDegree, 'primary', 'wave3')).toBe(null);

			const missingWave = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: 5 },
					primary: { wave3: null, wave5: null }
				}
			} as unknown as WaveSettings;
			expect(getWaveAlertPercent(missingWave, 'cycle', 'wave5')).toBe(null);
		});

		it('returns null for non-finite values', () => {
			const nonFinite: WaveSettings = {
				snap_to_wicks: null,
				alert_percents: {
					cycle: { wave3: NaN, wave5: Infinity },
					primary: { wave3: null, wave5: null }
				}
			};
			expect(getWaveAlertPercent(nonFinite, 'cycle', 'wave3')).toBe(null);
			expect(getWaveAlertPercent(nonFinite, 'cycle', 'wave5')).toBe(null);
		});
	});
});
