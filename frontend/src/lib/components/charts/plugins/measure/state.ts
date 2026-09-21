import type { Time } from 'lightweight-charts';
import { BaseCollectionToolState } from '../helpers/primitive/base-collection-state';
import type { DrawingPoint, MeasureDrawing } from '$lib/utils/finance/drawings';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies one draggable endpoint of a measure drawing. */
export interface MeasurePointTarget {
	id: string;
	pointIndex: 0 | 1;
}

/**
 * State for the Measure tool. Owns a collection of two-point drawings;
 * selection/hover/drag are keyed by drawing id + endpoint index. Anchors are
 * canonicalized to epoch seconds on ingestion so drawings are timeframe-independent.
 */
export class MeasureToolState extends BaseCollectionToolState<MeasureDrawing, MeasurePointTarget> {
	constructor(idFactory: () => string = generateUUID) {
		super(idFactory);
	}

	public getMeasures(): MeasureDrawing[] {
		return this.getDrawings();
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setMeasures(measures: MeasureDrawing[] | null | undefined): void {
		this.setDrawings(measures);
	}

	/**
	 * Adds an anchor for the current (in-progress) drawing. The second point
	 * completes a measure with a freshly generated id and exits drawing mode.
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
