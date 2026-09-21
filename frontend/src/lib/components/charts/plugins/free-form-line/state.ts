import type { Time } from 'lightweight-charts';
import { BaseCollectionToolState } from '../helpers/primitive/base-collection-state';
import type { DrawingPoint, LineDrawing } from '$lib/utils/finance/drawings';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies one draggable endpoint of a free-form line drawing. */
export interface LinePointTarget {
	id: string;
	pointIndex: 0 | 1;
}

/**
 * State for the free-form line tool. Owns a collection of two-point drawings;
 * selection/hover/drag are keyed by drawing id + endpoint index. Anchors are
 * canonicalized to epoch seconds on ingestion so drawings are timeframe-independent,
 * and both endpoints are freely draggable in time and price.
 */
export class LineToolState extends BaseCollectionToolState<LineDrawing, LinePointTarget> {
	constructor(idFactory: () => string = generateUUID) {
		super(idFactory);
	}

	public getLines(): LineDrawing[] {
		return this.getDrawings();
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setLines(lines: LineDrawing[] | null | undefined): void {
		this.setDrawings(lines);
	}

	/**
	 * Adds an anchor for the current (in-progress) drawing. The second point
	 * completes a line with a freshly generated id and exits drawing mode.
	 */
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
