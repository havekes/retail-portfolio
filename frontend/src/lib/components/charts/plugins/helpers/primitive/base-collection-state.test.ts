import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Time } from 'lightweight-charts';
import { BaseCollectionToolState } from './base-collection-state';
import type { DrawingPoint } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';

interface TestDrawing {
	id?: string;
	p1: DrawingPoint;
	p2?: DrawingPoint;
	visible?: boolean;
}

interface TestPointTarget {
	id: string;
	pointIndex?: 0 | 1;
}

class ConcreteTwoPointState extends BaseCollectionToolState<TestDrawing, TestPointTarget> {
	public addPoint(point: DrawingPoint): DrawingPoint {
		return this._addTwoPointDrawing(point);
	}

	public updatePoint(
		id: string,
		pointIndex: 0 | 1,
		update: { time?: Time; price?: number }
	): boolean {
		return this._updateTwoPointDrawing(id, pointIndex, update);
	}
}

describe('BaseCollectionToolState', () => {
	let idCounter: number;
	let state: ConcreteTwoPointState;

	beforeEach(() => {
		idCounter = 0;
		state = new ConcreteTwoPointState(() => `test-${++idCounter}`);
	});

	describe('initialization and cloning', () => {
		it('initializes with default empty state', () => {
			expect(state.getDrawings()).toEqual([]);
			expect(state.getPendingPoints()).toEqual([]);
			expect(state.getSelectedId()).toBeNull();
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.getHoveredLine()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();
			expect(state.isDrawingMode()).toBe(false);
		});

		it('deep-clones drawings returned from getDrawings', () => {
			state.setDrawings([
				{
					id: 'd1',
					p1: { time: 1000 as Time, price: 50 },
					p2: { time: 2000 as Time, price: 60 },
					visible: true
				}
			]);

			const drawings = state.getDrawings();
			drawings[0].p1.price = 999;
			if (drawings[0].p2) drawings[0].p2.price = 888;

			const fresh = state.getDrawings();
			expect(fresh[0].p1.price).toBe(50);
			expect(fresh[0].p2?.price).toBe(60);
		});
	});

	describe('setDrawings normalization and reactive loop prevention', () => {
		it('assigns generated IDs and normalizes anchor time', () => {
			const onDrawingsChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);

			state.setDrawings([
				{
					p1: { time: '2023-01-01', price: 100 },
					p2: { time: '2023-01-02', price: 110 }
				}
			]);

			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);
			const drawings = state.getDrawings();
			expect(drawings).toHaveLength(1);
			expect(drawings[0].id).toBe('test-1');
			expect(drawings[0].p1.time).toBe(normalizeDrawingTime('2023-01-01'));
			expect(drawings[0].p2?.time).toBe(normalizeDrawingTime('2023-01-02'));
		});

		it('does not fire drawingsChanged when setDrawings is called with identical normalized drawings', () => {
			state.setDrawings([
				{
					id: 'fixed-id',
					p1: { time: '2023-01-01', price: 100 },
					p2: { time: '2023-01-02', price: 110 },
					visible: true
				}
			]);

			const onDrawingsChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);

			// Call setDrawings with identical values (even with string time, which normalizes to the same epoch)
			state.setDrawings([
				{
					id: 'fixed-id',
					p1: { time: '2023-01-01', price: 100 },
					p2: { time: '2023-01-02', price: 110 },
					visible: true
				}
			]);

			expect(onDrawingsChanged).not.toHaveBeenCalled();
		});

		it('does not fire drawingsChanged when setDrawings is called on an already empty state', () => {
			const onDrawingsChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);

			state.setDrawings([]);
			state.setDrawings(null);
			state.setDrawings(undefined);

			expect(onDrawingsChanged).not.toHaveBeenCalled();
		});

		it('prunes selectedId if missing from incoming drawings', () => {
			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } },
				{ id: 'd2', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);
			state.select('d1');

			const onSelectionChanged = vi.fn();
			state.selectionChanged().subscribe(onSelectionChanged);

			// Incoming list only contains d2
			state.setDrawings([
				{ id: 'd2', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);

			expect(state.getSelectedId()).toBeNull();
			expect(onSelectionChanged).toHaveBeenCalledWith(null);
		});
	});

	describe('drawing mode and cancelation', () => {
		it('toggles drawing mode and deselects current selection', () => {
			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);
			state.select('d1');

			const onModeChanged = vi.fn();
			const onSelectionChanged = vi.fn();
			state.drawingModeChanged().subscribe(onModeChanged);
			state.selectionChanged().subscribe(onSelectionChanged);

			state.setDrawingMode(true);
			expect(state.isDrawingMode()).toBe(true);
			expect(state.getSelectedId()).toBeNull();
			expect(onModeChanged).toHaveBeenCalledWith(true);
			expect(onSelectionChanged).toHaveBeenCalledWith(null);

			// Redundant call does nothing
			state.setDrawingMode(true);
			expect(onModeChanged).toHaveBeenCalledTimes(1);
		});

		it('clears pending points and fires drawingsChanged on cancelDrawing', () => {
			state.setDrawingMode(true);
			state.addPoint({ time: 100 as Time, price: 50 });
			expect(state.getPendingPoints()).toHaveLength(1);

			const onDrawingsChanged = vi.fn();
			const onModeChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);
			state.drawingModeChanged().subscribe(onModeChanged);

			state.cancelDrawing();

			expect(state.getPendingPoints()).toEqual([]);
			expect(state.isDrawingMode()).toBe(false);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);
			expect(onModeChanged).toHaveBeenCalledWith(false);
		});

		it('clears pending points when setDrawingMode(false) is called', () => {
			state.setDrawingMode(true);
			state.addPoint({ time: 100 as Time, price: 50 });

			const onDrawingsChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);

			state.setDrawingMode(false);
			expect(state.getPendingPoints()).toEqual([]);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);
		});
	});

	describe('two-point drawing workflow', () => {
		it('completes a drawing after 2 points and exits drawing mode', () => {
			state.setDrawingMode(true);

			const onDrawingsChanged = vi.fn();
			const onModeChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);
			state.drawingModeChanged().subscribe(onModeChanged);

			const p1 = state.addPoint({ time: 100 as Time, price: 50 });
			expect(p1.price).toBe(50);
			expect(state.getPendingPoints()).toHaveLength(1);
			expect(state.getDrawings()).toHaveLength(0);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);

			const p2 = state.addPoint({ time: 200 as Time, price: 75 });
			expect(p2.price).toBe(75);
			expect(state.getPendingPoints()).toHaveLength(0);
			expect(state.getDrawings()).toHaveLength(1);
			expect(state.isDrawingMode()).toBe(false);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(2);
			expect(onModeChanged).toHaveBeenCalledWith(false);

			const drawing = state.getDrawings()[0];
			expect(drawing.id).toBe('test-1');
			expect(drawing.p1.price).toBe(50);
			expect(drawing.p2?.price).toBe(75);
		});

		it('updates point 0 or point 1 correctly via updatePoint', () => {
			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 50 }, p2: { time: 200 as Time, price: 75 } }
			]);

			const onDrawingsChanged = vi.fn();
			state.drawingsChanged().subscribe(onDrawingsChanged);

			const updated0 = state.updatePoint('d1', 0, { price: 55 });
			expect(updated0).toBe(true);
			expect(state.getDrawings()[0].p1.price).toBe(55);
			expect(state.getDrawings()[0].p2?.price).toBe(75);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);

			const updated1 = state.updatePoint('d1', 1, { time: 300 as Time, price: 80 });
			expect(updated1).toBe(true);
			expect(state.getDrawings()[0].p2?.time).toBe(normalizeDrawingTime(300 as Time));
			expect(state.getDrawings()[0].p2?.price).toBe(80);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(2);

			const missing = state.updatePoint('unknown', 0, { price: 10 });
			expect(missing).toBe(false);
			expect(onDrawingsChanged).toHaveBeenCalledTimes(2);
		});
	});

	describe('selection', () => {
		it('selects valid drawings and ignores nonexistent IDs', () => {
			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);

			const onSelectionChanged = vi.fn();
			state.selectionChanged().subscribe(onSelectionChanged);

			state.select('d1');
			expect(state.getSelectedId()).toBe('d1');
			expect(onSelectionChanged).toHaveBeenCalledWith('d1');

			// Same id again does not fire
			state.select('d1');
			expect(onSelectionChanged).toHaveBeenCalledTimes(1);

			// Invalid id is ignored
			state.select('does-not-exist');
			expect(state.getSelectedId()).toBe('d1');
			expect(onSelectionChanged).toHaveBeenCalledTimes(1);

			// Deselect
			state.select(null);
			expect(state.getSelectedId()).toBeNull();
			expect(onSelectionChanged).toHaveBeenCalledWith(null);
		});
	});

	describe('hover and drag targeting with pointIndex support', () => {
		it('manages hovered point with pointIndex disambiguation', () => {
			const onHoverChanged = vi.fn();
			state.hoverChanged().subscribe(onHoverChanged);

			state.setHoveredPoint({ id: 'd1', pointIndex: 0 });
			expect(state.getHoveredPoint()).toEqual({ id: 'd1', pointIndex: 0 });
			expect(onHoverChanged).toHaveBeenCalledWith({ id: 'd1', pointIndex: 0 });

			// Setting same target does not re-fire
			state.setHoveredPoint({ id: 'd1', pointIndex: 0 });
			expect(onHoverChanged).toHaveBeenCalledTimes(1);

			// Switching handle on the same drawing fires change
			state.setHoveredPoint({ id: 'd1', pointIndex: 1 });
			expect(state.getHoveredPoint()).toEqual({ id: 'd1', pointIndex: 1 });
			expect(onHoverChanged).toHaveBeenCalledTimes(2);

			state.setHoveredPoint(null);
			expect(state.getHoveredPoint()).toBeNull();
			expect(onHoverChanged).toHaveBeenCalledTimes(3);
		});

		it('manages hovered line by id', () => {
			const onHoveredLineChanged = vi.fn();
			state.hoveredLineChanged().subscribe(onHoveredLineChanged);

			state.setHoveredLine({ id: 'd1' });
			expect(state.getHoveredLine()).toEqual({ id: 'd1' });
			expect(onHoveredLineChanged).toHaveBeenCalledWith({ id: 'd1' });

			// Same id does not re-fire
			state.setHoveredLine({ id: 'd1' });
			expect(onHoveredLineChanged).toHaveBeenCalledTimes(1);

			state.setHoveredLine({ id: 'd2' });
			expect(state.getHoveredLine()).toEqual({ id: 'd2' });
			expect(onHoveredLineChanged).toHaveBeenCalledTimes(2);

			state.setHoveredLine(null);
			expect(state.getHoveredLine()).toBeNull();
			expect(onHoveredLineChanged).toHaveBeenCalledTimes(3);
		});

		it('manages dragging point with pointIndex disambiguation', () => {
			const onDragChanged = vi.fn();
			state.dragChanged().subscribe(onDragChanged);

			state.setDraggingPoint({ id: 'd1', pointIndex: 0 });
			expect(state.getDraggingPoint()).toEqual({ id: 'd1', pointIndex: 0 });
			expect(onDragChanged).toHaveBeenCalledWith({ id: 'd1', pointIndex: 0 });

			// Same target does not re-fire
			state.setDraggingPoint({ id: 'd1', pointIndex: 0 });
			expect(onDragChanged).toHaveBeenCalledTimes(1);

			// Switching handle fires change
			state.setDraggingPoint({ id: 'd1', pointIndex: 1 });
			expect(onDragChanged).toHaveBeenCalledTimes(2);

			state.setDraggingPoint(null);
			expect(state.getDraggingPoint()).toBeNull();
			expect(onDragChanged).toHaveBeenCalledTimes(3);
		});
	});

	describe('removeDrawing with cascade cleanup', () => {
		it('returns false when drawing is not found', () => {
			expect(state.removeDrawing('unknown')).toBe(false);
		});

		it('removes drawing and cascades cleanup to selection, hover, and drag targets', () => {
			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } },
				{ id: 'd2', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);

			state.select('d1');
			state.setHoveredPoint({ id: 'd1', pointIndex: 0 });
			state.setHoveredLine({ id: 'd1' });
			state.setDraggingPoint({ id: 'd1', pointIndex: 0 });

			const onDrawingsChanged = vi.fn();
			const onSelectionChanged = vi.fn();
			const onHoverChanged = vi.fn();
			const onHoveredLineChanged = vi.fn();
			const onDragChanged = vi.fn();

			state.drawingsChanged().subscribe(onDrawingsChanged);
			state.selectionChanged().subscribe(onSelectionChanged);
			state.hoverChanged().subscribe(onHoverChanged);
			state.hoveredLineChanged().subscribe(onHoveredLineChanged);
			state.dragChanged().subscribe(onDragChanged);

			const removed = state.removeDrawing('d1');
			expect(removed).toBe(true);
			expect(state.getDrawings()).toHaveLength(1);
			expect(state.getDrawings()[0].id).toBe('d2');

			expect(state.getSelectedId()).toBeNull();
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.getHoveredLine()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();

			expect(onDrawingsChanged).toHaveBeenCalledTimes(1);
			expect(onSelectionChanged).toHaveBeenCalledWith(null);
			expect(onHoverChanged).toHaveBeenCalledWith(null);
			expect(onHoveredLineChanged).toHaveBeenCalledWith(null);
			expect(onDragChanged).toHaveBeenCalledWith(null);
		});
	});

	describe('destroy', () => {
		it('destroys all delegates', () => {
			const dChanged = vi.fn();
			const mChanged = vi.fn();
			const sChanged = vi.fn();
			const hChanged = vi.fn();
			const hlChanged = vi.fn();
			const drChanged = vi.fn();

			state.drawingsChanged().subscribe(dChanged);
			state.drawingModeChanged().subscribe(mChanged);
			state.selectionChanged().subscribe(sChanged);
			state.hoverChanged().subscribe(hChanged);
			state.hoveredLineChanged().subscribe(hlChanged);
			state.dragChanged().subscribe(drChanged);

			state.destroy();

			state.setDrawings([
				{ id: 'd1', p1: { time: 100 as Time, price: 10 }, p2: { time: 200 as Time, price: 20 } }
			]);
			state.setDrawingMode(true);
			state.select('d1');
			state.setHoveredPoint({ id: 'd1' });
			state.setHoveredLine({ id: 'd1' });
			state.setDraggingPoint({ id: 'd1' });

			expect(dChanged).not.toHaveBeenCalled();
			expect(mChanged).not.toHaveBeenCalled();
			expect(sChanged).not.toHaveBeenCalled();
			expect(hChanged).not.toHaveBeenCalled();
			expect(hlChanged).not.toHaveBeenCalled();
			expect(drChanged).not.toHaveBeenCalled();
		});
	});
});
