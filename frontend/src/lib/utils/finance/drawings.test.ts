import { describe, it, expect } from 'vitest';
import type { UTCTimestamp } from 'lightweight-charts';
import {
	getSecurityDrawings,
	updateSecurityDrawings,
	addOrReplaceDrawing,
	removeSecurityDrawings,
	isSecurityDrawingsEmpty,
	normalizeSecurityDrawings,
	areDrawingPointsEqual,
	areDrawingsEqual,
	areDrawingCollectionsEqual,
	areSecurityDrawingsEqual,
	type MeasureDrawing,
	type HorizontalLineDrawing,
	type LineDrawing,
	type SecurityDrawingsMap
} from './drawings';

const EPOCH_2025_01_01 = 1735689600;
const EPOCH_2025_01_02 = 1735776000;

const measure: MeasureDrawing = {
	id: 'm1',
	p1: { time: '2024-01-01', price: 100 },
	p2: { time: '2024-01-02', price: 110 }
};

const measure2: MeasureDrawing = {
	id: 'm2',
	p1: { time: '2024-02-01', price: 200 },
	p2: { time: '2024-02-02', price: 220 }
};

const horizontal: HorizontalLineDrawing = {
	id: 'h1',
	p1: { time: '2024-01-03', price: 115 }
};

const line: LineDrawing = {
	id: 'l1',
	p1: { time: '2024-01-04', price: 120 },
	p2: { time: '2024-01-05', price: 90 }
};

describe('drawings finance utilities', () => {
	describe('getSecurityDrawings', () => {
		it('returns the per-security collection when present', () => {
			const state: SecurityDrawingsMap = { 'sec-1': { measures: [measure] } };
			expect(getSecurityDrawings(state, 'sec-1')).toEqual({ measures: [measure] });
		});

		it('returns null for missing keys, nullish state, or empty security id', () => {
			expect(getSecurityDrawings(null, 'sec-1')).toBeNull();
			expect(getSecurityDrawings(undefined, 'sec-1')).toBeNull();
			expect(getSecurityDrawings({}, 'sec-1')).toBeNull();
			expect(getSecurityDrawings({ 'sec-1': {} }, 'sec-2')).toBeNull();
			expect(getSecurityDrawings({ 'sec-1': {} }, '')).toBeNull();
		});
	});

	describe('updateSecurityDrawings', () => {
		it('adds a collection for a new security immutably', () => {
			const initial: SecurityDrawingsMap = {};
			const updated = updateSecurityDrawings(initial, 'sec-1', 'measures', [measure]);

			expect(updated).toEqual({ 'sec-1': { measures: [measure] } });
			expect(initial).toEqual({});
			expect(updated).not.toBe(initial);
		});

		it('replaces a collection for the same security/tool and preserves other tool types', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { measures: [measure], lines: [line] }
			};
			const updated = updateSecurityDrawings(initial, 'sec-1', 'measures', [measure2]);

			expect(updated['sec-1'].measures).toEqual([measure2]);
			expect(updated['sec-1'].lines).toEqual([line]);
			// input untouched
			expect(initial['sec-1'].measures).toEqual([measure]);
		});

		it('preserves other securities\u2019 drawings', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { measures: [measure] },
				'sec-2': { horizontalLines: [horizontal] }
			};
			const updated = updateSecurityDrawings(initial, 'sec-1', 'lines', [line]);

			expect(updated['sec-2']).toEqual({ horizontalLines: [horizontal] });
			expect(updated['sec-1']).toEqual({ measures: [measure], lines: [line] });
		});

		it('clears a collection when null is passed', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { measures: [measure], lines: [line] }
			};
			const updated = updateSecurityDrawings(initial, 'sec-1', 'measures', null);

			expect(updated['sec-1'].measures).toBeNull();
			expect(updated['sec-1'].lines).toEqual([line]);
		});

		it('returns a shallow copy for an empty security id and handles nullish input', () => {
			const initial: SecurityDrawingsMap = { 'sec-1': { measures: [measure] } };
			const copied = updateSecurityDrawings(initial, '', 'measures', [measure2]);
			expect(copied).toEqual(initial);
			expect(copied).not.toBe(initial);

			expect(updateSecurityDrawings(null, 'sec-1', 'lines', [line])).toEqual({
				'sec-1': { lines: [line] }
			});
		});
	});

	describe('addOrReplaceDrawing', () => {
		it('appends a drawing when its id is not present', () => {
			const initial: SecurityDrawingsMap = { 'sec-1': { measures: [measure] } };
			const updated = addOrReplaceDrawing(initial, 'sec-1', 'measures', measure2);

			expect(updated['sec-1'].measures).toEqual([measure, measure2]);
			expect(initial['sec-1'].measures).toEqual([measure]);
		});

		it('replaces a drawing with a matching id in place', () => {
			const replacement: MeasureDrawing = {
				id: 'm1',
				p1: { time: '2024-01-01', price: 999 },
				p2: { time: '2024-01-02', price: 111 }
			};
			const updated = addOrReplaceDrawing(
				{ 'sec-1': { measures: [measure, measure2] } },
				'sec-1',
				'measures',
				replacement
			);

			expect(updated['sec-1'].measures).toEqual([replacement, measure2]);
		});

		it('appends drawings without ids', () => {
			const noId: LineDrawing = {
				p1: { time: '2024-03-01', price: 50 },
				p2: { time: '2024-03-02', price: 60 }
			};
			const updated = addOrReplaceDrawing(undefined, 'sec-1', 'lines', noId);
			expect(updated['sec-1'].lines).toEqual([noId]);
		});

		it('preserves other tool types and other securities', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { horizontalLines: [horizontal] },
				'sec-2': { lines: [line] }
			};
			const updated = addOrReplaceDrawing(initial, 'sec-1', 'measures', measure);

			expect(updated['sec-1']).toEqual({ horizontalLines: [horizontal], measures: [measure] });
			expect(updated['sec-2']).toEqual({ lines: [line] });
		});
	});

	describe('removeSecurityDrawings', () => {
		it('removes a single drawing by id and preserves the others', () => {
			const initial: SecurityDrawingsMap = { 'sec-1': { measures: [measure, measure2] } };
			const updated = removeSecurityDrawings(initial, 'sec-1', 'measures', 'm1');

			expect(updated['sec-1'].measures).toEqual([measure2]);
			expect(initial['sec-1'].measures).toEqual([measure, measure2]);
		});

		it('clears the whole collection when no id is provided', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { measures: [measure], lines: [line] }
			};
			const updated = removeSecurityDrawings(initial, 'sec-1', 'measures');

			expect(updated['sec-1'].measures).toBeNull();
			expect(updated['sec-1'].lines).toEqual([line]);
		});

		it('sets the collection to null when the last drawing is removed', () => {
			const updated = removeSecurityDrawings(
				{ 'sec-1': { horizontalLines: [horizontal] } },
				'sec-1',
				'horizontalLines',
				'h1'
			);
			expect(updated['sec-1'].horizontalLines).toBeNull();
		});

		it('preserves other securities and handles missing security ids', () => {
			const initial: SecurityDrawingsMap = {
				'sec-1': { measures: [measure] },
				'sec-2': { lines: [line] }
			};
			const updated = removeSecurityDrawings(initial, 'sec-1', 'measures');

			expect(updated['sec-2']).toEqual({ lines: [line] });
			expect(updated['sec-1'].measures).toBeNull();

			const copied = removeSecurityDrawings(initial, '', 'measures');
			expect(copied).toEqual(initial);
			expect(copied).not.toBe(initial);
		});
	});

	describe('isSecurityDrawingsEmpty', () => {
		it('treats null/undefined and empty collections as empty', () => {
			expect(isSecurityDrawingsEmpty(null)).toBe(true);
			expect(isSecurityDrawingsEmpty(undefined)).toBe(true);
			expect(isSecurityDrawingsEmpty({})).toBe(true);
			expect(isSecurityDrawingsEmpty({ measures: [], horizontalLines: null })).toBe(true);
		});

		it('returns false when any collection has entries', () => {
			expect(isSecurityDrawingsEmpty({ measures: [measure] })).toBe(false);
			expect(isSecurityDrawingsEmpty({ horizontalLines: [horizontal] })).toBe(false);
			expect(isSecurityDrawingsEmpty({ lines: [line] })).toBe(false);
		});
	});

	describe('normalizeSecurityDrawings', () => {
		it('converts date-string and BusinessDay anchors to epoch seconds', () => {
			const legacy: SecurityDrawingsMap = {
				'sec-1': {
					measures: [
						{
							id: 'm1',
							p1: { time: '2025-01-01', price: 100 },
							p2: { time: '2025-01-02', price: 110 }
						}
					],
					horizontalLines: [
						{ id: 'h1', p1: { time: { year: 2025, month: 1, day: 1 }, price: 90 } }
					],
					lines: [
						{
							id: 'l1',
							p1: { time: '2025-01-01', price: 80 },
							p2: { time: '2025-01-02', price: 70 }
						}
					]
				}
			};

			const normalized = normalizeSecurityDrawings(legacy['sec-1']);

			expect(normalized?.measures?.[0].p1).toEqual({ time: EPOCH_2025_01_01, price: 100 });
			expect(normalized?.measures?.[0].p2).toEqual({ time: EPOCH_2025_01_02, price: 110 });
			expect(normalized?.horizontalLines?.[0].p1).toEqual({ time: EPOCH_2025_01_01, price: 90 });
			expect(normalized?.lines?.[0].p1).toEqual({ time: EPOCH_2025_01_01, price: 80 });
			expect(normalized?.lines?.[0].p2).toEqual({ time: EPOCH_2025_01_02, price: 70 });
			// ids and visibility are preserved
			expect(normalized?.measures?.[0].id).toBe('m1');
			expect(normalized?.horizontalLines?.[0].id).toBe('h1');
		});

		it('is idempotent for already-normalized epoch anchors', () => {
			const epochDrawings: SecurityDrawingsMap = {
				'sec-1': {
					measures: [
						{
							id: 'm-epoch',
							p1: { time: EPOCH_2025_01_01 as UTCTimestamp, price: 100 },
							p2: { time: EPOCH_2025_01_02 as UTCTimestamp, price: 110 }
						}
					]
				}
			};
			const normalized = normalizeSecurityDrawings(epochDrawings['sec-1']);
			expect(normalized?.measures?.[0].p1.time).toBe(EPOCH_2025_01_01);
			expect(normalizeSecurityDrawings(normalized)?.measures).toEqual(normalized?.measures);
		});

		it('preserves null/undefined collections and nullish input', () => {
			expect(normalizeSecurityDrawings(null)).toBeNull();
			expect(normalizeSecurityDrawings(undefined)).toBeNull();
			expect(normalizeSecurityDrawings({ measures: null })).toEqual({ measures: null });
			expect(normalizeSecurityDrawings({ lines: undefined })?.lines).toBeUndefined();
		});
	});

	describe('areDrawingPointsEqual', () => {
		it('compares price and time using canonical epoch normalization', () => {
			expect(
				areDrawingPointsEqual(
					{ time: '2024-01-01', price: 100 },
					{ time: '2024-01-01', price: 100 }
				)
			).toBe(true);
			// A legacy date-string anchor equals its epoch form
			expect(
				areDrawingPointsEqual(
					{ time: 1735689600 as UTCTimestamp, price: 100 },
					{ time: '2025-01-01', price: 100 }
				)
			).toBe(true);
			// A BusinessDay anchor equals its epoch form
			expect(
				areDrawingPointsEqual(
					{ time: { year: 2025, month: 1, day: 1 }, price: 100 },
					{ time: 1735689600 as UTCTimestamp, price: 100 }
				)
			).toBe(true);
			expect(
				areDrawingPointsEqual(
					{ time: '2024-01-01', price: 100 },
					{ time: '2024-01-01', price: 101 }
				)
			).toBe(false);
			expect(
				areDrawingPointsEqual(
					{ time: '2024-01-01', price: 100 },
					{ time: '2024-01-02', price: 100 }
				)
			).toBe(false);
		});

		it('treats missing points symmetrically', () => {
			expect(areDrawingPointsEqual(null, undefined)).toBe(true);
			expect(areDrawingPointsEqual({ time: '2024-01-01', price: 100 }, null)).toBe(false);
			expect(areDrawingPointsEqual(null, { time: '2024-01-01', price: 100 })).toBe(false);
		});
	});

	describe('areDrawingsEqual', () => {
		it('detects point changes', () => {
			const changed: MeasureDrawing = { ...measure, p2: { time: '2024-01-02', price: 999 } };
			expect(areDrawingsEqual(measure, measure)).toBe(true);
			expect(areDrawingsEqual(measure, changed)).toBe(false);
		});

		it('detects visibility changes but normalizes undefined to visible', () => {
			expect(areDrawingsEqual(measure, { ...measure, visible: true })).toBe(true);
			expect(areDrawingsEqual(measure, { ...measure, visible: undefined })).toBe(true);
			expect(areDrawingsEqual({ ...measure, visible: false }, { ...measure, visible: true })).toBe(
				false
			);
			expect(areDrawingsEqual({ ...measure, visible: false }, measure)).toBe(false);
		});

		it('detects id changes and one-point vs two-point shape mismatches', () => {
			expect(areDrawingsEqual(measure, { ...measure, id: 'other' })).toBe(false);
			expect(areDrawingsEqual(measure, { id: 'm1', p1: measure.p1 } as HorizontalLineDrawing)).toBe(
				false
			);
		});

		it('treats both nullish as equal and one nullish as unequal', () => {
			expect(areDrawingsEqual(null, undefined)).toBe(true);
			expect(areDrawingsEqual(measure, null)).toBe(false);
			expect(areDrawingsEqual(undefined, line)).toBe(false);
		});
	});

	describe('areDrawingCollectionsEqual', () => {
		it('compares order-sensitively and normalizes missing to empty', () => {
			expect(areDrawingCollectionsEqual(null, [])).toBe(true);
			expect(areDrawingCollectionsEqual(undefined, null)).toBe(true);
			expect(areDrawingCollectionsEqual([measure], [measure])).toBe(true);
			expect(areDrawingCollectionsEqual([measure, measure2], [measure2, measure])).toBe(false);
			expect(areDrawingCollectionsEqual([measure], [measure, measure2])).toBe(false);
		});
	});

	describe('areSecurityDrawingsEqual', () => {
		it('treats missing, null and empty collections as equal', () => {
			expect(areSecurityDrawingsEqual(undefined, null)).toBe(true);
			expect(areSecurityDrawingsEqual({}, { measures: [], lines: null })).toBe(true);
			expect(areSecurityDrawingsEqual(undefined, { measures: [] })).toBe(true);
		});

		it('detects content and visibility differences', () => {
			expect(areSecurityDrawingsEqual({ measures: [measure] }, { measures: [measure] })).toBe(true);
			expect(
				areSecurityDrawingsEqual(
					{ measures: [measure] },
					{ measures: [{ ...measure, visible: false }] }
				)
			).toBe(false);
			expect(areSecurityDrawingsEqual({ measures: [measure] }, { measures: [measure2] })).toBe(
				false
			);
			expect(areSecurityDrawingsEqual({ lines: [line] }, { measures: [measure] })).toBe(false);
		});
	});
});
