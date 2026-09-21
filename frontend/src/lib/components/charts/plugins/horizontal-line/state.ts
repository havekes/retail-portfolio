import { BaseCollectionToolState } from '../helpers/primitive/base-collection-state';
import type { DrawingPoint, HorizontalLineDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies the single draggable handle of a horizontal line drawing. */
export interface HorizontalLineTarget {
	id: string;
}

/**
 * State for the Horizontal Line tool. Unlike Measure (two anchors), a single
 * click is enough to complete a line, so `addPoint` commits immediately and
 * exits drawing mode. Selection/hover/drag are keyed by drawing id only; there
 * is no point index. Anchors are canonicalized to epoch seconds on ingestion so
 * drawings are timeframe-independent, and the anchor time is never mutated by
 * drags — dragging only moves the price, keeping the line horizontal.
 */
export class HorizontalLineToolState extends BaseCollectionToolState<
	HorizontalLineDrawing,
	HorizontalLineTarget
> {
	constructor(idFactory: () => string = generateUUID) {
		super(idFactory);
	}

	public getHorizontalLines(): HorizontalLineDrawing[] {
		return this.getDrawings();
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setHorizontalLines(lines: HorizontalLineDrawing[] | null | undefined): void {
		this.setDrawings(lines);
	}

	/**
	 * Commits a horizontal line at the clicked point immediately (one click
	 * completes the drawing) and exits drawing mode.
	 */
	public addPoint(point: DrawingPoint): DrawingPoint {
		const newPoint: DrawingPoint = {
			time: normalizeDrawingTime(point.time),
			price: point.price
		};

		this._drawings = [...this._drawings, { id: this._idFactory(), p1: newPoint, visible: true }];
		this.setDrawingMode(false);
		this._drawingsChanged.fire(this.getDrawings());
		return newPoint;
	}

	/** Updates the line's price only; the anchor time never moves (stays horizontal). */
	public updatePoint(id: string, update: { price?: number }): boolean {
		const index = this._drawings.findIndex((line) => line.id === id);
		if (index < 0) return false;
		const current = this._drawings[index];
		if (update.price === undefined) return false;
		const p1 = { ...current.p1, price: update.price };
		const next = [...this._drawings];
		next[index] = { ...current, p1 };
		this._drawings = next;
		this._drawingsChanged.fire(this.getDrawings());
		return true;
	}
}
