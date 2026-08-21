import { describe, it, expect } from 'vitest';
import {
	computeWaveAlertLevels,
	reconcileWaveAlerts,
	roundTo8dp,
	type WaveAlertLevel
} from './wave-alerts';
import type { WaveSettings, SecurityElliottWaves } from './elliott-wave';
import type { PriceAlert } from '$lib/api/alertsService';

const cycleWaves: SecurityElliottWaves = {
	cycle: {
		points: [
			{ wave: 0, time: '2024-01-01', price: 50 },
			{ wave: 1, time: '2024-01-02', price: 100 },
			{ wave: 2, time: '2024-01-03', price: 80 },
			{ wave: 3, time: '2024-01-04', price: 150 },
			{ wave: 4, time: '2024-01-05', price: 120 },
			{ wave: 5, time: '2024-01-06', price: 200 }
		]
	}
};

const bothDegreesWaves: SecurityElliottWaves = {
	cycle: cycleWaves.cycle,
	primary: {
		points: [
			{ wave: 0, time: '2024-02-01', price: 40 },
			{ wave: 1, time: '2024-02-02', price: 90 },
			{ wave: 2, time: '2024-02-03', price: 70 },
			{ wave: 3, time: '2024-02-04', price: 120 },
			{ wave: 4, time: '2024-02-05', price: 100 },
			{ wave: 5, time: '2024-02-06', price: 160 }
		]
	}
};

function settings(percents: Partial<WaveSettings['alert_percents']> = {}): WaveSettings {
	return {
		alert_percents: {
			cycle: { wave3: null, wave5: null },
			primary: { wave3: null, wave5: null },
			...percents
		}
	};
}

describe('roundTo8dp', () => {
	it('rounds to 8 decimal places', () => {
		expect(roundTo8dp(107.99100000000001)).toBe(107.991);
		expect(roundTo8dp(107.99999999)).toBe(107.99999999);
		expect(roundTo8dp(108.000000004)).toBe(108);
	});
});

describe('computeWaveAlertLevels', () => {
	it('returns [] when currentPrice is not a finite positive number', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		expect(computeWaveAlertLevels(s, cycleWaves, null)).toEqual([]);
		expect(computeWaveAlertLevels(s, cycleWaves, 0)).toEqual([]);
		expect(computeWaveAlertLevels(s, cycleWaves, NaN)).toEqual([]);
		expect(computeWaveAlertLevels(s, cycleWaves, -5)).toEqual([]);
	});

	it('computes level = target × percent/100 and above condition when level > current', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		// cycle wave3 target 150 × 90% = 135 (above current 100)
		// cycle wave5 target 200 × 90% = 180 (above current 100)
		const result = computeWaveAlertLevels(s, cycleWaves, 100);
		expect(result).toEqual([
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' },
			{ degree: 'cycle', wave: 'wave5', level: 180, condition: 'above' }
		]);
	});

	it('uses below condition when level < current', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		const result = computeWaveAlertLevels(s, cycleWaves, 200);
		expect(result).toEqual([
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'below' },
			{ degree: 'cycle', wave: 'wave5', level: 180, condition: 'below' }
		]);
	});

	it('handles floating-point percent math at 8dp', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		const waves: SecurityElliottWaves = {
			cycle: { points: [{ wave: 3, time: '2024-01-04', price: 119.99 }] }
		};
		// 119.99 × 90/100 = 107.991 (8dp)
		const result = computeWaveAlertLevels(s, waves, 100);
		expect(result[0].level).toBe(107.991);
	});

	it('skips a level equal to currentPrice', () => {
		// level = 100 when current = 100 → skip
		const s = settings({ cycle: { wave3: 100, wave5: 100 } });
		const waves: SecurityElliottWaves = {
			cycle: { points: [{ wave: 3, time: '2024-01-04', price: 100 }] }
		};
		expect(computeWaveAlertLevels(s, waves, 100)).toEqual([]);
	});

	it('per-degree independence: cycle set + primary null → only cycle alerts', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		const result = computeWaveAlertLevels(s, bothDegreesWaves, 100);
		expect(result.map((l) => l.degree)).toEqual(['cycle', 'cycle']);
	});

	it('per-degree independence: primary set + cycle null → only primary alerts', () => {
		const s = settings({ primary: { wave3: 50, wave5: 50 } });
		const result = computeWaveAlertLevels(s, bothDegreesWaves, 100);
		// primary wave3 120 × 50% = 60, wave5 160 × 50% = 80
		expect(result).toEqual([
			{ degree: 'primary', wave: 'wave3', level: 60, condition: 'below' },
			{ degree: 'primary', wave: 'wave5', level: 80, condition: 'below' }
		]);
	});

	it('all percents null → []', () => {
		expect(computeWaveAlertLevels(settings(), bothDegreesWaves, 100)).toEqual([]);
	});

	it('null settings → []', () => {
		expect(computeWaveAlertLevels(null, bothDegreesWaves, 100)).toEqual([]);
	});

	it('missing target for a degree → no alert for that degree', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		// cycle has a wave3 point but no wave5 point → only wave3 alert
		const waves: SecurityElliottWaves = {
			cycle: { points: [{ wave: 3, time: '2024-01-04', price: 150 }] }
		};
		const result = computeWaveAlertLevels(s, waves, 100);
		expect(result).toEqual([{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' }]);
	});

	it('respects wave3Target/wave5Target overrides', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 } });
		const waves: SecurityElliottWaves = {
			cycle: {
				points: [{ wave: 3, time: '2024-01-04', price: 150 }],
				wave3Target: 175,
				wave5Target: 250
			}
		};
		const result = computeWaveAlertLevels(s, waves, 100);
		expect(result).toEqual([
			{ degree: 'cycle', wave: 'wave3', level: 157.5, condition: 'above' },
			{ degree: 'cycle', wave: 'wave5', level: 225, condition: 'above' }
		]);
	});

	it('both degrees fully configured → up to 4 alerts', () => {
		const s = settings({ cycle: { wave3: 90, wave5: 90 }, primary: { wave3: 50, wave5: 50 } });
		const result = computeWaveAlertLevels(s, bothDegreesWaves, 100);
		expect(result).toHaveLength(4);
		expect(new Set(result.map((l) => `${l.degree}:${l.wave}`))).toEqual(
			new Set(['cycle:wave3', 'cycle:wave5', 'primary:wave3', 'primary:wave5'])
		);
	});
});

describe('reconcileWaveAlerts', () => {
	function waveAlert(over: Partial<PriceAlert>): PriceAlert {
		return {
			id: 1,
			security_id: 'sec-1',
			user_id: 'user-1',
			target_price: 135,
			condition: 'above',
			source: 'wave',
			triggered_at: null,
			created_at: '2024-01-01',
			...over
		};
	}

	it('creates missing desired levels and deletes stale wave alerts, keeping matching', () => {
		const existing: PriceAlert[] = [
			waveAlert({ id: 1, target_price: 135, condition: 'above' }), // matches desired
			waveAlert({ id: 2, target_price: 999, condition: 'above' }) // stale
		];
		const desired: WaveAlertLevel[] = [
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' },
			{ degree: 'cycle', wave: 'wave5', level: 180, condition: 'above' }
		];
		const { toCreate, toDelete } = reconcileWaveAlerts(existing, desired);
		expect(toDelete).toEqual([waveAlert({ id: 2, target_price: 999, condition: 'above' })]);
		expect(toCreate).toEqual([{ degree: 'cycle', wave: 'wave5', level: 180, condition: 'above' }]);
	});

	it('never deletes manual alerts (a matching manual alert is left as-is and the wave alert is still created)', () => {
		const existing: PriceAlert[] = [
			waveAlert({ id: 1, source: 'manual', target_price: 135, condition: 'above' }),
			waveAlert({ id: 2, source: 'manual', target_price: 999, condition: 'below' })
		];
		const desired: WaveAlertLevel[] = [
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' }
		];
		const { toCreate, toDelete } = reconcileWaveAlerts(existing, desired);
		// Manual alerts are never deleted...
		expect(toDelete).toEqual([]);
		// ...and a manual alert at the same level does NOT suppress the wave alert create.
		expect(toCreate).toEqual(desired);
	});

	it('creates missing when no matching wave alert exists', () => {
		const { toCreate, toDelete } = reconcileWaveAlerts(
			[],
			[{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' }]
		);
		expect(toCreate).toEqual([{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' }]);
		expect(toDelete).toEqual([]);
	});

	it('dedupes desired levels with identical (level, condition) even from different degrees', () => {
		const desired: WaveAlertLevel[] = [
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' },
			{ degree: 'primary', wave: 'wave3', level: 135, condition: 'above' }
		];
		const { toCreate } = reconcileWaveAlerts([], desired);
		expect(toCreate).toHaveLength(1);
		expect(toCreate[0]).toEqual(desired[0]);
	});

	it('normalizes string target_price from server Decimal', () => {
		const existing: PriceAlert[] = [
			waveAlert({ id: 1, target_price: '135' as unknown as number, condition: 'above' })
		];
		const desired: WaveAlertLevel[] = [
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' }
		];
		const { toCreate, toDelete } = reconcileWaveAlerts(existing, desired);
		expect(toDelete).toEqual([]);
		expect(toCreate).toEqual([]);
	});

	it('is idempotent — fully-applied state yields empty sets', () => {
		const existing: PriceAlert[] = [
			waveAlert({ id: 1, target_price: 135, condition: 'above' }),
			waveAlert({ id: 2, target_price: 180, condition: 'above' })
		];
		const desired: WaveAlertLevel[] = [
			{ degree: 'cycle', wave: 'wave3', level: 135, condition: 'above' },
			{ degree: 'cycle', wave: 'wave5', level: 180, condition: 'above' }
		];
		expect(reconcileWaveAlerts(existing, desired)).toEqual({ toCreate: [], toDelete: [] });
	});
});
