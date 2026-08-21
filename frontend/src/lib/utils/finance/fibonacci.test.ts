import { describe, it, expect } from 'vitest';
import {
	calculateRetracementLevels,
	calculateExtensionLevels,
	formatFibLevelLabel,
	updateSecurityFibonacciTools,
	getSecurityFibonacciTools,
	areFibPointsEqual,
	areFibLevelConfigsEqual,
	areRetracementDrawingsEqual,
	areExtensionDrawingsEqual,
	areFibonacciToolsEqual,
	DEFAULT_FIB_RETRACEMENT_LEVELS,
	DEFAULT_FIB_EXTENSION_LEVELS,
	type FibPoint,
	type FibLevelConfig,
	type FibRetracementDrawing,
	type FibExtensionDrawing,
	type SecurityFibonacciTools
} from './fibonacci';

describe('fibonacci finance utilities', () => {
	const samplePoint1: FibPoint = { time: '2024-01-01', price: 100 };
	const samplePoint2: FibPoint = { time: '2024-01-02', price: 200 };
	const samplePoint3: FibPoint = { time: '2024-01-03', price: 150 };

	describe('DEFAULT constants', () => {
		it('defines standard retracement levels', () => {
			const ratios = DEFAULT_FIB_RETRACEMENT_LEVELS.map((l) => l.ratio);
			expect(ratios).toEqual([0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.618]);
			expect(DEFAULT_FIB_RETRACEMENT_LEVELS.every((l) => l.enabled === true)).toBe(true);
			expect(DEFAULT_FIB_RETRACEMENT_LEVELS.every((l) => typeof l.color === 'string')).toBe(true);
		});

		it('defines standard extension levels', () => {
			const ratios = DEFAULT_FIB_EXTENSION_LEVELS.map((l) => l.ratio);
			expect(ratios).toEqual([0.0, 0.382, 0.5, 0.618, 1.0, 1.272, 1.618, 2.0, 2.618, 3.618, 4.236]);
			expect(DEFAULT_FIB_EXTENSION_LEVELS.every((l) => l.enabled === true)).toBe(true);
			expect(DEFAULT_FIB_EXTENSION_LEVELS.every((l) => typeof l.color === 'string')).toBe(true);
		});
	});

	describe('formatFibLevelLabel', () => {
		it('formats standard ratio and price with 2 decimal places by default', () => {
			expect(formatFibLevelLabel(0.618, 42.5)).toBe('0.618 (42.50)');
			expect(formatFibLevelLabel(0.5, 100)).toBe('0.5 (100.00)');
			expect(formatFibLevelLabel(0, 0)).toBe('0 (0.00)');
		});

		it('supports custom decimal places', () => {
			expect(formatFibLevelLabel(0.382, 123.4567, 3)).toBe('0.382 (123.457)');
			expect(formatFibLevelLabel(1.0, 50, 0)).toBe('1 (50)');
		});

		it('returns empty string when ratio is invalid', () => {
			expect(formatFibLevelLabel(NaN, 100)).toBe('');
			expect(formatFibLevelLabel(Infinity, 100)).toBe('');
			expect(formatFibLevelLabel(null, 100)).toBe('');
			expect(formatFibLevelLabel(undefined, 100)).toBe('');
		});

		it('returns ratio only when price is invalid', () => {
			expect(formatFibLevelLabel(0.618, NaN)).toBe('0.618');
			expect(formatFibLevelLabel(0.618, Infinity)).toBe('0.618');
			expect(formatFibLevelLabel(0.618, null)).toBe('0.618');
			expect(formatFibLevelLabel(0.618, undefined)).toBe('0.618');
		});
	});

	describe('calculateRetracementLevels', () => {
		it('calculates correct levels for uptrend (P1 swing low to P2 swing high)', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 100 };
			const p2: FibPoint = { time: '2024-01-02', price: 200 };
			const levels = calculateRetracementLevels(p1, p2);

			expect(levels).toHaveLength(DEFAULT_FIB_RETRACEMENT_LEVELS.length);

			// delta = 200 - 100 = 100. price = 200 - ratio * 100
			const findLevel = (r: number) => levels.find((l) => Math.abs(l.ratio - r) < 0.0001);

			expect(findLevel(0.0)?.price).toBeCloseTo(200.0, 4);
			expect(findLevel(0.0)?.label).toBe('0 (200.00)');

			expect(findLevel(0.236)?.price).toBeCloseTo(176.4, 4);
			expect(findLevel(0.236)?.label).toBe('0.236 (176.40)');

			expect(findLevel(0.382)?.price).toBeCloseTo(161.8, 4);
			expect(findLevel(0.382)?.label).toBe('0.382 (161.80)');

			expect(findLevel(0.5)?.price).toBeCloseTo(150.0, 4);
			expect(findLevel(0.5)?.label).toBe('0.5 (150.00)');

			expect(findLevel(0.618)?.price).toBeCloseTo(138.2, 4);
			expect(findLevel(0.618)?.label).toBe('0.618 (138.20)');

			expect(findLevel(0.786)?.price).toBeCloseTo(121.4, 4);
			expect(findLevel(0.786)?.label).toBe('0.786 (121.40)');

			expect(findLevel(1.0)?.price).toBeCloseTo(100.0, 4);
			expect(findLevel(1.0)?.label).toBe('1 (100.00)');

			expect(findLevel(1.618)?.price).toBeCloseTo(38.2, 4);
			expect(findLevel(1.618)?.label).toBe('1.618 (38.20)');
		});

		it('calculates correct levels for downtrend (P1 swing high to P2 swing low)', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 200 };
			const p2: FibPoint = { time: '2024-01-02', price: 100 };
			const levels = calculateRetracementLevels(p1, p2);

			// delta = 100 - 200 = -100. price = 100 - ratio * (-100) = 100 + ratio * 100
			const findLevel = (r: number) => levels.find((l) => Math.abs(l.ratio - r) < 0.0001);

			expect(findLevel(0.0)?.price).toBeCloseTo(100.0, 4);
			expect(findLevel(0.236)?.price).toBeCloseTo(123.6, 4);
			expect(findLevel(0.382)?.price).toBeCloseTo(138.2, 4);
			expect(findLevel(0.5)?.price).toBeCloseTo(150.0, 4);
			expect(findLevel(0.618)?.price).toBeCloseTo(161.8, 4);
			expect(findLevel(0.786)?.price).toBeCloseTo(178.6, 4);
			expect(findLevel(1.0)?.price).toBeCloseTo(200.0, 4);
			expect(findLevel(1.618)?.price).toBeCloseTo(261.8, 4);
		});

		it('handles custom level configs with custom colors and enabled state', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 50 };
			const p2: FibPoint = { time: '2024-01-02', price: 150 };
			const customConfigs: FibLevelConfig[] = [
				{ ratio: 0.5, color: '#FF0000', enabled: true },
				{ ratio: 0.618, color: '#00FF00', enabled: false }
			];

			const levels = calculateRetracementLevels(p1, p2, customConfigs);
			expect(levels).toHaveLength(2);
			expect(levels[0]).toEqual({
				ratio: 0.5,
				price: 100,
				formattedPrice: '100.00',
				label: '0.5 (100.00)',
				color: '#FF0000',
				enabled: true
			});
			expect(levels[1]).toEqual({
				ratio: 0.618,
				price: 88.2,
				formattedPrice: '88.20',
				label: '0.618 (88.20)',
				color: '#00FF00',
				enabled: false
			});
		});

		it('supports numeric ratios array directly', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 0 };
			const p2: FibPoint = { time: '2024-01-02', price: 100 };
			const levels = calculateRetracementLevels(p1, p2, [0, 0.5, 1]);

			expect(levels).toHaveLength(3);
			expect(levels[1].price).toBe(50);
			expect(levels[1].enabled).toBe(true);
			expect(levels[1].color).toBeUndefined();
		});

		it('handles flat prices (P1 === P2)', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 150 };
			const p2: FibPoint = { time: '2024-01-02', price: 150 };
			const levels = calculateRetracementLevels(p1, p2);

			expect(levels.length).toBeGreaterThan(0);
			levels.forEach((l) => {
				expect(l.price).toBe(150);
			});
		});

		it('handles negative prices correctly', () => {
			const p1: FibPoint = { time: '2024-01-01', price: -50 };
			const p2: FibPoint = { time: '2024-01-02', price: -10 };
			// delta = -10 - (-50) = 40. price = -10 - ratio * 40
			const levels = calculateRetracementLevels(p1, p2, [0.5]);
			expect(levels[0].price).toBeCloseTo(-30, 4);
		});

		it('returns empty array when inputs are missing, null, undefined, or non-finite', () => {
			expect(calculateRetracementLevels(null, samplePoint2)).toEqual([]);
			expect(calculateRetracementLevels(samplePoint1, null)).toEqual([]);
			expect(calculateRetracementLevels(undefined, undefined)).toEqual([]);
			expect(calculateRetracementLevels({ time: '2024-01-01', price: NaN }, samplePoint2)).toEqual(
				[]
			);
			expect(
				calculateRetracementLevels(samplePoint1, { time: '2024-01-02', price: Infinity })
			).toEqual([]);
			expect(
				calculateRetracementLevels(samplePoint1, { time: '2024-01-02', price: -Infinity })
			).toEqual([]);
			expect(
				calculateRetracementLevels(
					{ time: '2024-01-01', price: 'bad' } as unknown as FibPoint,
					samplePoint2
				)
			).toEqual([]);
			expect(calculateRetracementLevels(samplePoint1, samplePoint2, [])).toEqual([]);
		});

		it('skips invalid items in custom configs without throwing', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 100 };
			const p2: FibPoint = { time: '2024-01-02', price: 200 };
			const levels = calculateRetracementLevels(p1, p2, [
				null,
				{ ratio: NaN },
				{ ratio: 0.5 }
			] as unknown as FibLevelConfig[]);
			expect(levels).toHaveLength(1);
			expect(levels[0].ratio).toBe(0.5);
		});
	});

	describe('calculateExtensionLevels', () => {
		it('calculates correct projected levels for 3-point bullish extension', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 100 }; // start
			const p2: FibPoint = { time: '2024-01-02', price: 200 }; // wave 1 top (move = +100)
			const p3: FibPoint = { time: '2024-01-03', price: 150 }; // wave 2 retracement trough
			const levels = calculateExtensionLevels(p1, p2, p3);

			expect(levels).toHaveLength(DEFAULT_FIB_EXTENSION_LEVELS.length);

			// price = 150 + ratio * 100
			const findLevel = (r: number) => levels.find((l) => Math.abs(l.ratio - r) < 0.0001);

			expect(findLevel(0.0)?.price).toBeCloseTo(150.0, 4);
			expect(findLevel(0.382)?.price).toBeCloseTo(188.2, 4);
			expect(findLevel(0.5)?.price).toBeCloseTo(200.0, 4);
			expect(findLevel(0.618)?.price).toBeCloseTo(211.8, 4);
			expect(findLevel(1.0)?.price).toBeCloseTo(250.0, 4);
			expect(findLevel(1.272)?.price).toBeCloseTo(277.2, 4);
			expect(findLevel(1.618)?.price).toBeCloseTo(311.8, 4);
			expect(findLevel(2.0)?.price).toBeCloseTo(350.0, 4);
			expect(findLevel(2.618)?.price).toBeCloseTo(411.8, 4);
			expect(findLevel(3.618)?.price).toBeCloseTo(511.8, 4);
			expect(findLevel(4.236)?.price).toBeCloseTo(573.6, 4);
		});

		it('calculates correct projected levels for 3-point bearish extension', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 200 }; // start
			const p2: FibPoint = { time: '2024-01-02', price: 100 }; // trough (move = -100)
			const p3: FibPoint = { time: '2024-01-03', price: 160 }; // bounce level
			const levels = calculateExtensionLevels(p1, p2, p3);

			// price = 160 + ratio * (-100)
			const findLevel = (r: number) => levels.find((l) => Math.abs(l.ratio - r) < 0.0001);

			expect(findLevel(0.0)?.price).toBeCloseTo(160.0, 4);
			expect(findLevel(0.618)?.price).toBeCloseTo(98.2, 4);
			expect(findLevel(1.0)?.price).toBeCloseTo(60.0, 4);
			expect(findLevel(1.618)?.price).toBeCloseTo(-1.8, 4);
		});

		it('supports custom extension configs', () => {
			const customConfigs: FibLevelConfig[] = [
				{ ratio: 1.0, color: '#123456', enabled: true },
				{ ratio: 1.618, color: '#654321', enabled: false }
			];
			const levels = calculateExtensionLevels(
				samplePoint1,
				samplePoint2,
				samplePoint3,
				customConfigs
			);

			expect(levels).toHaveLength(2);
			expect(levels[0].price).toBe(250);
			expect(levels[0].color).toBe('#123456');
			expect(levels[0].enabled).toBe(true);
			expect(levels[1].price).toBe(311.8);
			expect(levels[1].color).toBe('#654321');
			expect(levels[1].enabled).toBe(false);
		});

		it('handles flat origin/peak (P1 === P2)', () => {
			const p1: FibPoint = { time: '2024-01-01', price: 100 };
			const p2: FibPoint = { time: '2024-01-02', price: 100 };
			const p3: FibPoint = { time: '2024-01-03', price: 80 };
			const levels = calculateExtensionLevels(p1, p2, p3);

			expect(levels.length).toBeGreaterThan(0);
			levels.forEach((l) => {
				expect(l.price).toBe(80);
			});
		});

		it('returns empty array when any input point is invalid or non-finite', () => {
			expect(calculateExtensionLevels(null, samplePoint2, samplePoint3)).toEqual([]);
			expect(calculateExtensionLevels(samplePoint1, null, samplePoint3)).toEqual([]);
			expect(calculateExtensionLevels(samplePoint1, samplePoint2, null)).toEqual([]);
			expect(
				calculateExtensionLevels({ time: '2024-01-01', price: NaN }, samplePoint2, samplePoint3)
			).toEqual([]);
			expect(
				calculateExtensionLevels(
					samplePoint1,
					{ time: '2024-01-02', price: Infinity },
					samplePoint3
				)
			).toEqual([]);
			expect(
				calculateExtensionLevels(samplePoint1, samplePoint2, {
					time: '2024-01-03',
					price: -Infinity
				})
			).toEqual([]);
			expect(calculateExtensionLevels(samplePoint1, samplePoint2, samplePoint3, [])).toEqual([]);
		});
	});

	describe('immutable state helpers', () => {
		const sampleRetracement: FibRetracementDrawing = {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			levels: DEFAULT_FIB_RETRACEMENT_LEVELS,
			extendLines: true,
			visible: true
		};

		const sampleExtension: FibExtensionDrawing = {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			p3: { time: '2024-01-03', price: 150 },
			levels: DEFAULT_FIB_EXTENSION_LEVELS,
			extendLines: false,
			visible: true
		};

		describe('updateSecurityFibonacciTools', () => {
			it('immutably sets retracement for a security using toolType string', () => {
				const initial: Record<string, SecurityFibonacciTools> = {
					'sec-1': {
						retracement: null,
						extension: sampleExtension
					}
				};

				const updated = updateSecurityFibonacciTools(
					initial,
					'sec-1',
					'retracement',
					sampleRetracement
				);

				expect(updated).not.toBe(initial);
				expect(updated['sec-1']).not.toBe(initial['sec-1']);
				expect(updated['sec-1'].retracement).toEqual(sampleRetracement);
				expect(updated['sec-1'].extension).toEqual(sampleExtension);
				expect(initial['sec-1'].retracement).toBeNull();
			});

			it('immutably sets extension for a security using toolType string', () => {
				const initial: Record<string, SecurityFibonacciTools> = {};
				const updated = updateSecurityFibonacciTools(
					initial,
					'sec-2',
					'extension',
					sampleExtension
				);

				expect(updated['sec-2'].extension).toEqual(sampleExtension);
				expect(updated['sec-2'].retracement).toBeUndefined();
				expect(initial['sec-2']).toBeUndefined();
			});

			it('updates tools using partial object', () => {
				const initial: Record<string, SecurityFibonacciTools> = {
					'sec-1': { retracement: sampleRetracement, extension: sampleExtension }
				};

				const updated = updateSecurityFibonacciTools(initial, 'sec-1', {
					retracement: null
				});

				expect(updated['sec-1'].retracement).toBeNull();
				expect(updated['sec-1'].extension).toEqual(sampleExtension);
			});

			it('clears security tools when null is passed', () => {
				const initial: Record<string, SecurityFibonacciTools> = {
					'sec-1': { retracement: sampleRetracement, extension: sampleExtension }
				};

				const updated = updateSecurityFibonacciTools(initial, 'sec-1', null);
				expect(updated['sec-1']).toEqual({ retracement: null, extension: null });
			});

			it('handles undefined/null initial state gracefully', () => {
				const updated = updateSecurityFibonacciTools(
					null,
					'sec-1',
					'retracement',
					sampleRetracement
				);
				expect(updated['sec-1'].retracement).toEqual(sampleRetracement);
			});

			it('handles empty securityId gracefully', () => {
				const initial: Record<string, SecurityFibonacciTools> = { 'sec-1': {} };
				const updated = updateSecurityFibonacciTools(initial, '', 'retracement', sampleRetracement);
				expect(updated).toEqual(initial);
			});
		});

		describe('getSecurityFibonacciTools', () => {
			it('returns tools for a matching security', () => {
				const state: Record<string, SecurityFibonacciTools> = {
					'sec-1': { retracement: sampleRetracement, extension: null }
				};
				expect(getSecurityFibonacciTools(state, 'sec-1')).toEqual({
					retracement: sampleRetracement,
					extension: null
				});
			});

			it('returns null when security is not found or inputs nullish', () => {
				const state: Record<string, SecurityFibonacciTools> = {
					'sec-1': { retracement: sampleRetracement }
				};
				expect(getSecurityFibonacciTools(state, 'sec-unknown')).toBeNull();
				expect(getSecurityFibonacciTools(null, 'sec-1')).toBeNull();
				expect(getSecurityFibonacciTools(undefined, 'sec-1')).toBeNull();
				expect(getSecurityFibonacciTools(state, '')).toBeNull();
			});
		});

		describe('structural equality helpers', () => {
			it('areFibPointsEqual compares points accurately', () => {
				expect(areFibPointsEqual(null, null)).toBe(true);
				expect(areFibPointsEqual(undefined, undefined)).toBe(true);
				expect(areFibPointsEqual(samplePoint1, null)).toBe(false);
				expect(areFibPointsEqual(samplePoint1, { ...samplePoint1 })).toBe(true);
				expect(areFibPointsEqual(samplePoint1, { ...samplePoint1, price: 105 })).toBe(false);
				expect(areFibPointsEqual(samplePoint1, { ...samplePoint1, time: '2024-01-05' })).toBe(
					false
				);
			});

			it('areFibLevelConfigsEqual compares configs accurately', () => {
				expect(areFibLevelConfigsEqual(null, null)).toBe(true);
				expect(areFibLevelConfigsEqual([], [])).toBe(true);
				expect(
					areFibLevelConfigsEqual(DEFAULT_FIB_RETRACEMENT_LEVELS, [
						...DEFAULT_FIB_RETRACEMENT_LEVELS
					])
				).toBe(true);
				expect(
					areFibLevelConfigsEqual([{ ratio: 0.5, enabled: true }], [{ ratio: 0.5, enabled: false }])
				).toBe(false);
				expect(
					areFibLevelConfigsEqual([{ ratio: 0.5, color: '#111' }], [{ ratio: 0.5, color: '#222' }])
				).toBe(false);
				expect(areFibLevelConfigsEqual([{ ratio: 0.5 }], [{ ratio: 0.618 }])).toBe(false);
				expect(areFibLevelConfigsEqual([{ ratio: 0.5 }], [{ ratio: 0.5 }, { ratio: 0.618 }])).toBe(
					false
				);
			});

			it('areRetracementDrawingsEqual compares retracements accurately', () => {
				expect(areRetracementDrawingsEqual(null, null)).toBe(true);
				expect(areRetracementDrawingsEqual(sampleRetracement, { ...sampleRetracement })).toBe(true);
				expect(areRetracementDrawingsEqual(sampleRetracement, null)).toBe(false);
				expect(
					areRetracementDrawingsEqual(sampleRetracement, {
						...sampleRetracement,
						p1: { ...sampleRetracement.p1, price: 99 }
					})
				).toBe(false);
				expect(
					areRetracementDrawingsEqual(sampleRetracement, {
						...sampleRetracement,
						extendLines: false
					})
				).toBe(false);
				expect(
					areRetracementDrawingsEqual(sampleRetracement, { ...sampleRetracement, visible: false })
				).toBe(false);
			});

			it('areExtensionDrawingsEqual compares extensions accurately', () => {
				expect(areExtensionDrawingsEqual(null, null)).toBe(true);
				expect(areExtensionDrawingsEqual(sampleExtension, { ...sampleExtension })).toBe(true);
				expect(areExtensionDrawingsEqual(sampleExtension, null)).toBe(false);
				expect(
					areExtensionDrawingsEqual(sampleExtension, {
						...sampleExtension,
						p3: { ...sampleExtension.p3, price: 140 }
					})
				).toBe(false);
				expect(
					areExtensionDrawingsEqual(sampleExtension, { ...sampleExtension, extendLines: true })
				).toBe(false);
			});

			it('areFibonacciToolsEqual compares complete security tools', () => {
				expect(areFibonacciToolsEqual(null, null)).toBe(true);
				expect(areFibonacciToolsEqual(undefined, undefined)).toBe(true);
				expect(
					areFibonacciToolsEqual(
						{ retracement: sampleRetracement, extension: sampleExtension },
						{ retracement: { ...sampleRetracement }, extension: { ...sampleExtension } }
					)
				).toBe(true);
				expect(
					areFibonacciToolsEqual(
						{ retracement: sampleRetracement, extension: null },
						{ retracement: sampleRetracement, extension: sampleExtension }
					)
				).toBe(false);
				expect(
					areFibonacciToolsEqual(
						{ retracement: null, extension: sampleExtension },
						{ retracement: sampleRetracement, extension: sampleExtension }
					)
				).toBe(false);
			});
		});
	});
});
