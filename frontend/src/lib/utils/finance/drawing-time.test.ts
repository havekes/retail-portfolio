import { describe, it, expect } from 'vitest';
import type { BusinessDay, UTCTimestamp } from 'lightweight-charts';
import { normalizeDrawingTime } from './drawing-time';
import { normalizeWaveIds, areSecurityElliottWavesEqual } from './elliott-wave';
import { normalizeSecurityFibonacciTools, normalizeFibPoint, areFibPointsEqual } from './fibonacci';

const epochOf = (iso: string): number => Math.floor(new Date(iso).getTime() / 1000);

describe('normalizeDrawingTime', () => {
	it('passes through numeric epoch anchors', () => {
		expect(normalizeDrawingTime(1704067200 as UTCTimestamp)).toBe(1704067200);
		expect(normalizeDrawingTime(1704067200)).toBe(1704067200);
	});

	it('converts date strings (daily/weekly/monthly candles) to UTC epoch seconds', () => {
		expect(normalizeDrawingTime('2024-01-15')).toBe(epochOf('2024-01-15T00:00:00Z'));
		expect(normalizeDrawingTime('2024-02-01')).toBe(epochOf('2024-02-01T00:00:00Z'));
	});

	it('converts BusinessDay anchors to UTC epoch seconds', () => {
		const bday: BusinessDay = { year: 2024, month: 6, day: 20 };
		expect(normalizeDrawingTime(bday)).toBe(epochOf('2024-06-20T00:00:00Z'));
	});

	it('falls back to 0 for invalid or missing anchors', () => {
		expect(normalizeDrawingTime('not-a-date')).toBe(0);
		expect(normalizeDrawingTime(null)).toBe(0);
		expect(normalizeDrawingTime(undefined)).toBe(0);
	});
});

describe('legacy anchor normalization', () => {
	it('normalizes FibPoint anchors and compares representations of the same instant as equal', () => {
		const epochPoint = normalizeFibPoint({
			time: epochOf('2024-01-15T00:00:00Z') as UTCTimestamp,
			price: 10
		});
		const legacyPoint = normalizeFibPoint({ time: '2024-01-15', price: 10 });

		expect(epochPoint).toEqual({ time: epochOf('2024-01-15T00:00:00Z'), price: 10 });
		expect(legacyPoint).toEqual(epochPoint);
		expect(areFibPointsEqual(epochPoint, legacyPoint)).toBe(true);
		expect(areFibPointsEqual(epochPoint, { time: '2024-01-16', price: 10 })).toBe(false);
	});

	it('normalizes every Fibonacci drawing anchor', () => {
		const normalized = normalizeSecurityFibonacciTools({
			retracement: { p1: { time: '2024-01-15', price: 10 }, p2: { time: '2024-01-20', price: 20 } },
			extension: {
				p1: { time: '2024-01-15', price: 10 },
				p2: { time: '2024-01-20', price: 20 },
				p3: { time: '2024-01-25', price: 15 }
			}
		});

		expect(normalized.retracement?.p1.time).toBe(epochOf('2024-01-15T00:00:00Z'));
		expect(normalized.retracement?.p2.time).toBe(epochOf('2024-01-20T00:00:00Z'));
		expect(normalized.extension?.p3.time).toBe(epochOf('2024-01-25T00:00:00Z'));
	});

	it('normalizes wave point anchors and derives matching ids for legacy and epoch forms', () => {
		// Empty ids exercise deterministic id derivation from the normalized anchors.
		const legacy = [
			{
				id: '',
				degree: 'cycle' as const,
				type: 'impulse' as const,
				points: [{ wave: 0 as const, time: '2024-01-15', price: 10 }]
			}
		];
		const epoch = [
			{
				id: '',
				degree: 'cycle' as const,
				type: 'impulse' as const,
				points: [
					{ wave: 0 as const, time: epochOf('2024-01-15T00:00:00Z') as UTCTimestamp, price: 10 }
				]
			}
		];

		const normalizedLegacy = normalizeWaveIds(legacy);
		const normalizedEpoch = normalizeWaveIds(epoch);

		expect(normalizedLegacy[0].points[0].time).toBe(epochOf('2024-01-15T00:00:00Z'));
		expect(normalizedLegacy[0].id).toBe(normalizedEpoch[0].id);
		expect(areSecurityElliottWavesEqual({ waves: legacy }, { waves: epoch })).toBe(true);
	});
});
