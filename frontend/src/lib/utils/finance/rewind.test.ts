import { describe, it, expect, vi } from 'vitest';
import {
	captureSnapshot,
	appendSnapshot,
	getSnapshots,
	findSnapshotAtOrBefore,
	areSnapshotsEqual,
	type RewindDataWindow,
	type RewindDrawings,
	type RewindSnapshot
} from './rewind';
import type { DegreeWaveCount, SecurityElliottWaves } from './elliott-wave';
import type { SecurityFibonacciTools } from './fibonacci';

describe('rewind finance utilities', () => {
	const sampleWaveCount: DegreeWaveCount = {
		type: 'impulse',
		points: [
			{ wave: 0, time: '2024-01-01', price: 100 },
			{ wave: 1, time: '2024-01-02', price: 120 },
			{ wave: 2, time: '2024-01-03', price: 110 },
			{ wave: 3, time: '2024-01-04', price: 150 },
			{ wave: 4, time: '2024-01-05', price: 140 },
			{ wave: 5, time: '2024-01-06', price: 180 }
		],
		wave3Target: 160,
		wave5Target: 190
	};

	const sampleElliottWaves: SecurityElliottWaves = {
		primary: sampleWaveCount
	};

	const sampleFibTools: SecurityFibonacciTools = {
		retracement: {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			levels: [{ ratio: 0.618, color: '#089981', enabled: true }]
		}
	};

	const sampleDrawings: RewindDrawings = {
		elliott_waves: sampleElliottWaves,
		fibonacci_tools: sampleFibTools
	};

	const sampleDataWindow: RewindDataWindow = {
		first: '2024-01-01',
		last: '2024-02-01'
	};

	describe('captureSnapshot', () => {
		it('generates non-empty unique id across two calls and spies on crypto.randomUUID', () => {
			const uuidSpy = vi.spyOn(crypto, 'randomUUID');
			const snap1 = captureSnapshot(sampleDrawings, sampleDataWindow);
			const snap2 = captureSnapshot(sampleDrawings, sampleDataWindow);

			expect(uuidSpy).toHaveBeenCalled();
			expect(snap1.id).toBeDefined();
			expect(snap1.id.length).toBeGreaterThan(0);
			expect(snap2.id).toBeDefined();
			expect(snap2.id.length).toBeGreaterThan(0);
			expect(snap1.id).not.toBe(snap2.id);

			uuidSpy.mockRestore();
		});

		it('sets captured_at equal to injected now.toISOString()', () => {
			const injectedTime = new Date('2026-08-27T10:00:00.000Z');
			const snap = captureSnapshot(sampleDrawings, sampleDataWindow, injectedTime);

			expect(snap.captured_at).toBe('2026-08-27T10:00:00.000Z');
			expect(snap.drawings).toEqual(sampleDrawings);
			expect(snap.data_window).toEqual(sampleDataWindow);
		});

		it('defaults captured_at to ~now when omitted', () => {
			const before = Date.now();
			const snap = captureSnapshot(sampleDrawings, sampleDataWindow);
			const after = Date.now();

			const parsed = Date.parse(snap.captured_at);
			expect(parsed).toBeGreaterThanOrEqual(before);
			expect(parsed).toBeLessThanOrEqual(after);
		});
	});

	describe('appendSnapshot', () => {
		it('appends without mutating the input map or array', () => {
			const snap1: RewindSnapshot = {
				id: 's1',
				captured_at: '2026-08-27T10:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};
			const snap2: RewindSnapshot = {
				id: 's2',
				captured_at: '2026-08-27T11:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};

			const originalMap: Record<string, RewindSnapshot[]> = {
				AAPL: [snap1]
			};

			const updated = appendSnapshot(originalMap, 'AAPL', snap2);

			// Input not mutated
			expect(originalMap['AAPL']).toHaveLength(1);
			expect(originalMap['AAPL'][0]).toBe(snap1);

			// New map and array returned
			expect(updated).not.toBe(originalMap);
			expect(updated['AAPL']).not.toBe(originalMap['AAPL']);
			expect(updated['AAPL']).toHaveLength(2);
			expect(updated['AAPL'][0]).toBe(snap1);
			expect(updated['AAPL'][1]).toBe(snap2);
		});

		it('creates key when missing or allSnapshots is null/undefined', () => {
			const snap: RewindSnapshot = {
				id: 's1',
				captured_at: '2026-08-27T10:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};

			const fromNull = appendSnapshot(null, 'MSFT', snap);
			expect(fromNull['MSFT']).toEqual([snap]);

			const fromUndefined = appendSnapshot(undefined, 'GOOG', snap);
			expect(fromUndefined['GOOG']).toEqual([snap]);

			const fromEmpty = appendSnapshot({}, 'NVDA', snap);
			expect(fromEmpty['NVDA']).toEqual([snap]);
		});

		it('maintains oldest→newest order across multiple appends', () => {
			const s1 = captureSnapshot(
				sampleDrawings,
				sampleDataWindow,
				new Date('2026-08-27T10:00:00.000Z')
			);
			const s2 = captureSnapshot(
				sampleDrawings,
				sampleDataWindow,
				new Date('2026-08-27T11:00:00.000Z')
			);
			const s3 = captureSnapshot(
				sampleDrawings,
				sampleDataWindow,
				new Date('2026-08-27T12:00:00.000Z')
			);

			let map: Record<string, RewindSnapshot[]> = {};
			map = appendSnapshot(map, 'AAPL', s1);
			map = appendSnapshot(map, 'AAPL', s2);
			map = appendSnapshot(map, 'AAPL', s3);

			expect(map['AAPL'].map((s) => s.captured_at)).toEqual([
				'2026-08-27T10:00:00.000Z',
				'2026-08-27T11:00:00.000Z',
				'2026-08-27T12:00:00.000Z'
			]);
		});
	});

	describe('getSnapshots', () => {
		it('returns an empty array for missing key, null, undefined, or empty input', () => {
			expect(getSnapshots(null, 'AAPL')).toEqual([]);
			expect(getSnapshots(undefined, 'AAPL')).toEqual([]);
			expect(getSnapshots({}, 'AAPL')).toEqual([]);
			expect(getSnapshots({ AAPL: [] }, 'AAPL')).toEqual([]);
			expect(getSnapshots({ AAPL: [] }, '')).toEqual([]);
		});

		it('returns snapshots sorted ascending even when input array is out-of-order', () => {
			const sEarly: RewindSnapshot = {
				id: 's1',
				captured_at: '2026-08-27T08:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};
			const sMid: RewindSnapshot = {
				id: 's2',
				captured_at: '2026-08-27T10:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};
			const sLate: RewindSnapshot = {
				id: 's3',
				captured_at: '2026-08-27T12:00:00.000Z',
				drawings: sampleDrawings,
				data_window: sampleDataWindow
			};

			const outOfOrderList = [sLate, sEarly, sMid];
			const store = { AAPL: outOfOrderList };

			const result = getSnapshots(store, 'AAPL');

			expect(result.map((s) => s.id)).toEqual(['s1', 's2', 's3']);
			// Does not mutate input array
			expect(outOfOrderList[0].id).toBe('s3');
			expect(outOfOrderList[1].id).toBe('s1');
			expect(outOfOrderList[2].id).toBe('s2');
			expect(result).not.toBe(outOfOrderList);
		});
	});

	describe('findSnapshotAtOrBefore', () => {
		const s1: RewindSnapshot = {
			id: 's1',
			captured_at: '2026-08-27T10:00:00.000Z',
			drawings: sampleDrawings,
			data_window: sampleDataWindow
		};
		const s2: RewindSnapshot = {
			id: 's2',
			captured_at: '2026-08-27T11:00:00.000Z',
			drawings: sampleDrawings,
			data_window: sampleDataWindow
		};
		const s3: RewindSnapshot = {
			id: 's3',
			captured_at: '2026-08-27T12:00:00.000Z',
			drawings: sampleDrawings,
			data_window: sampleDataWindow
		};

		const store = { AAPL: [s1, s2, s3] };

		it('returns null before-the-first', () => {
			const result = findSnapshotAtOrBefore(store, 'AAPL', new Date('2026-08-27T09:59:59.999Z'));
			expect(result).toBeNull();
		});

		it('returns exact match when time equals captured_at', () => {
			const result = findSnapshotAtOrBefore(store, 'AAPL', new Date('2026-08-27T11:00:00.000Z'));
			expect(result).toBe(s2);
		});

		it('returns latest snapshot at-or-before intermediate time', () => {
			const result = findSnapshotAtOrBefore(store, 'AAPL', new Date('2026-08-27T11:30:00.000Z'));
			expect(result).toBe(s2);
		});

		it('returns last snapshot after-the-last', () => {
			const result = findSnapshotAtOrBefore(store, 'AAPL', new Date('2026-08-27T13:00:00.000Z'));
			expect(result).toBe(s3);
		});

		it('returns null when store is missing or empty', () => {
			expect(findSnapshotAtOrBefore(null, 'AAPL', new Date())).toBeNull();
			expect(findSnapshotAtOrBefore(undefined, 'AAPL', new Date())).toBeNull();
			expect(findSnapshotAtOrBefore({}, 'AAPL', new Date())).toBeNull();
			expect(findSnapshotAtOrBefore({ AAPL: [] }, 'AAPL', new Date())).toBeNull();
			expect(findSnapshotAtOrBefore(store, 'NONEXISTENT', new Date())).toBeNull();
		});

		it('returns null for invalid Date', () => {
			expect(findSnapshotAtOrBefore(store, 'AAPL', new Date('invalid'))).toBeNull();
		});
	});

	describe('areSnapshotsEqual', () => {
		const baseSnapshot: RewindSnapshot = {
			id: 'uuid-1',
			captured_at: '2026-08-27T10:00:00.000Z',
			drawings: sampleDrawings,
			data_window: sampleDataWindow
		};

		it('returns true for equal content with different id and captured_at', () => {
			const differentMeta: RewindSnapshot = {
				id: 'uuid-999',
				captured_at: '2026-08-27T12:00:00.000Z',
				drawings: {
					elliott_waves: {
						primary: {
							type: 'impulse',
							points: [
								{ wave: 0, time: '2024-01-01', price: 100 },
								{ wave: 1, time: '2024-01-02', price: 120 },
								{ wave: 2, time: '2024-01-03', price: 110 },
								{ wave: 3, time: '2024-01-04', price: 150 },
								{ wave: 4, time: '2024-01-05', price: 140 },
								{ wave: 5, time: '2024-01-06', price: 180 }
							],
							wave3Target: 160,
							wave5Target: 190
						}
					},
					fibonacci_tools: {
						retracement: {
							p1: { time: '2024-01-01', price: 100 },
							p2: { time: '2024-01-02', price: 200 },
							levels: [{ ratio: 0.618, color: '#089981', enabled: true }]
						}
					}
				},
				data_window: {
					first: '2024-01-01',
					last: '2024-02-01'
				}
			};

			expect(areSnapshotsEqual(baseSnapshot, differentMeta)).toBe(true);
		});

		it('returns true for both null or both undefined', () => {
			expect(areSnapshotsEqual(null, null)).toBe(true);
			expect(areSnapshotsEqual(undefined, undefined)).toBe(true);
			expect(areSnapshotsEqual(null, undefined)).toBe(true);
		});

		it('returns false when one is null/undefined and the other is defined', () => {
			expect(areSnapshotsEqual(baseSnapshot, null)).toBe(false);
			expect(areSnapshotsEqual(null, baseSnapshot)).toBe(false);
			expect(areSnapshotsEqual(baseSnapshot, undefined)).toBe(false);
			expect(areSnapshotsEqual(undefined, baseSnapshot)).toBe(false);
		});

		it('returns false when drawings differ via Elliott Wave inequality', () => {
			const differingWaves: RewindSnapshot = {
				...baseSnapshot,
				drawings: {
					...baseSnapshot.drawings,
					elliott_waves: {
						primary: {
							...sampleWaveCount,
							wave3Target: 999
						}
					}
				}
			};
			expect(areSnapshotsEqual(baseSnapshot, differingWaves)).toBe(false);
		});

		it('returns false when drawings differ via Fibonacci inequality', () => {
			const differingFib: RewindSnapshot = {
				...baseSnapshot,
				drawings: {
					...baseSnapshot.drawings,
					fibonacci_tools: {
						retracement: {
							p1: { time: '2024-01-01', price: 999 },
							p2: { time: '2024-01-02', price: 200 },
							levels: [{ ratio: 0.618, color: '#089981', enabled: true }]
						}
					}
				}
			};
			expect(areSnapshotsEqual(baseSnapshot, differingFib)).toBe(false);
		});

		it('returns false when data_window differs', () => {
			const differingFirst: RewindSnapshot = {
				...baseSnapshot,
				data_window: { first: '2024-01-05', last: '2024-02-01' }
			};
			expect(areSnapshotsEqual(baseSnapshot, differingFirst)).toBe(false);

			const differingLast: RewindSnapshot = {
				...baseSnapshot,
				data_window: { first: '2024-01-01', last: '2024-02-15' }
			};
			expect(areSnapshotsEqual(baseSnapshot, differingLast)).toBe(false);
		});

		it('returns true when data_window compares string vs number', () => {
			const snapWithNumbers: RewindSnapshot = {
				id: 's1',
				captured_at: '2026-08-27T10:00:00.000Z',
				drawings: {},
				data_window: { first: 1700000000, last: 1700100000 }
			};
			const snapWithStrings: RewindSnapshot = {
				id: 's2',
				captured_at: '2026-08-27T11:00:00.000Z',
				drawings: {},
				data_window: { first: '1700000000', last: '1700100000' }
			};
			expect(areSnapshotsEqual(snapWithNumbers, snapWithStrings)).toBe(true);
		});

		it('handles nullish drawing comparisons gracefully', () => {
			const snapEmptyDrawings1: RewindSnapshot = {
				id: 's1',
				captured_at: '2026-08-27T10:00:00.000Z',
				drawings: {},
				data_window: sampleDataWindow
			};
			const snapEmptyDrawings2: RewindSnapshot = {
				id: 's2',
				captured_at: '2026-08-27T11:00:00.000Z',
				drawings: {
					elliott_waves: null,
					fibonacci_tools: null
				},
				data_window: sampleDataWindow
			};
			expect(areSnapshotsEqual(snapEmptyDrawings1, snapEmptyDrawings2)).toBe(true);
		});
	});
});
