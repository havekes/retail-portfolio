import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import type { DrawingPoint, MeasureDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies one draggable endpoint of a measure drawing. */
export interface MeasurePointTarget {
	id: string;
	pointIndex: 0 | 1;
}

function normalizeDrawingPoint(point: DrawingPoint): DrawingPoint {
	return { time: normalizeDrawingTime(point.time), price: point.price };
}

function normalizeMeasure(drawing: MeasureDrawing, idFactory: () => string): MeasureDrawing {
	return {
		id: drawing.id ?? idFactory(),
		p1: normalizeDrawingPoint(drawing.p1),
		p2: normalizeDrawingPoint(drawing.p2),
		visible: drawing.visible
	};
}

/**
 * State for the Measure tool. Unlike Fibonacci (one drawing per tool), Measure
 * owns a collection of two-point drawings; selection/hover/drag are keyed by
 * drawing id + endpoint index. Anchors are canonicalized to epoch seconds on
 * ingestion so drawings are timeframe-independent.
 */
export class MeasureToolState {
	private _measures: MeasureDrawing[] = [];
	private _pendingPoints: DrawingPoint[] = [];
	private _selectedId: string | null = null;
	private _hovered: MeasurePointTarget | null = null;
	private _hoveredLine: MeasurePointTarget | null = null;
	private _dragging: MeasurePointTarget | null = null;
	private _isDrawingMode: boolean = false;

	private readonly _idFactory: () => string;

	private _drawingsChanged: Delegate<MeasureDrawing[]> = new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _selectionChanged: Delegate<string | null> = new Delegate();
	private _hoverChanged: Delegate<MeasurePointTarget | null> = new Delegate();
	private _hoveredLineChanged: Delegate<MeasurePointTarget | null> = new Delegate();
	private _dragChanged: Delegate<MeasurePointTarget | null> = new Delegate();

	constructor(idFactory: () => string = generateUUID) {
		this._idFactory = idFactory;
	}

	public drawingsChanged(): ISubscription<MeasureDrawing[]> {
		return this._drawingsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public selectionChanged(): ISubscription<string | null> {
		return this._selectionChanged;
	}

	public hoverChanged(): ISubscription<MeasurePointTarget | null> {
		return this._hoverChanged;
	}

	public hoveredLineChanged(): ISubscription<MeasurePointTarget | null> {
		return this._hoveredLineChanged;
	}

	public dragChanged(): ISubscription<MeasurePointTarget | null> {
		return this._dragChanged;
	}

	public getMeasures(): MeasureDrawing[] {
		return this._measures.map((m) => ({
			...m,
			p1: { ...m.p1 },
			p2: { ...m.p2 }
		}));
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setMeasures(measures: MeasureDrawing[] | null | undefined): void {
		const next = (measures ?? []).map((m) => normalizeMeasure(m, this._idFactory));
		this._measures = next;
		if (this._selectedId !== null && !next.some((m) => m.id === this._selectedId)) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		this._drawingsChanged.fire(this.getMeasures());
	}

	public getPendingPoints(): DrawingPoint[] {
		return this._pendingPoints.map((p) => ({ ...p }));
	}

	public isDrawingMode(): boolean {
		return this._isDrawingMode;
	}

	public setDrawingMode(enabled: boolean): void {
		if (this._isDrawingMode === enabled) return;
		this._isDrawingMode = enabled;
		if (enabled && this._selectedId !== null) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		if (!enabled) {
			const hadPending = this._pendingPoints.length > 0;
			this._pendingPoints = [];
			if (hadPending) {
				this._drawingsChanged.fire(this.getMeasures());
			}
		}
		this._drawingModeChanged.fire(enabled);
	}

	public cancelDrawing(): void {
		const hadPending = this._pendingPoints.length > 0;
		this._pendingPoints = [];
		if (hadPending) {
			this._drawingsChanged.fire(this.getMeasures());
		}
		this.setDrawingMode(false);
	}

	/**
	 * Adds an anchor for the current (in-progress) drawing. The second point
	 * completes a measure with a freshly generated id and exits drawing mode.
	 */
	public addPoint(point: DrawingPoint): DrawingPoint {
		const newPoint: DrawingPoint = {
			time: normalizeDrawingTime(point.time),
			price: point.price
		};

		if (this._pendingPoints.length >= 2) {
			this._pendingPoints = [];
		}
		this._pendingPoints.push(newPoint);

		if (this._pendingPoints.length === 2) {
			const [p1, p2] = this._pendingPoints;
			this._measures = [...this._measures, { id: this._idFactory(), p1, p2, visible: true }];
			this._pendingPoints = [];
			this.setDrawingMode(false);
		}
		this._drawingsChanged.fire(this.getMeasures());
		return newPoint;
	}

	public updatePoint(
		id: string,
		pointIndex: 0 | 1,
		update: { time?: Time; price?: number }
	): boolean {
		const index = this._measures.findIndex((m) => m.id === id);
		if (index < 0) return false;
		const current = this._measures[index];
		const p1 = { ...current.p1 };
		const p2 = { ...current.p2 };
		if (pointIndex === 0) {
			if (update.time !== undefined) p1.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p1.price = update.price;
		} else {
			if (update.time !== undefined) p2.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p2.price = update.price;
		}
		const next = [...this._measures];
		next[index] = { ...current, p1, p2 };
		this._measures = next;
		this._drawingsChanged.fire(this.getMeasures());
		return true;
	}

	public removeDrawing(id: string): boolean {
		const next = this._measures.filter((m) => m.id !== id);
		if (next.length === this._measures.length) return false;
		this._measures = next;
		if (this._selectedId === id) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		if (this._hovered?.id === id) this.setHoveredPoint(null);
		if (this._hoveredLine?.id === id) this.setHoveredLine(null);
		if (this._dragging?.id === id) this.setDraggingPoint(null);
		this._drawingsChanged.fire(this.getMeasures());
		return true;
	}

	public getSelectedId(): string | null {
		return this._selectedId;
	}

	public select(id: string | null): void {
		if (id !== null && !this._measures.some((m) => m.id === id)) return;
		if (this._selectedId !== id) {
			this._selectedId = id;
			this._selectionChanged.fire(id);
		}
	}

	public setHoveredPoint(point: MeasurePointTarget | null): void {
		const changed =
			this._hovered?.id !== point?.id || this._hovered?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._hovered = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): MeasurePointTarget | null {
		return this._hovered;
	}

	public setHoveredLine(line: MeasurePointTarget | null): void {
		const changed = this._hoveredLine?.id !== line?.id;
		if (changed) {
			this._hoveredLine = line;
			this._hoveredLineChanged.fire(line);
		}
	}

	public getHoveredLine(): MeasurePointTarget | null {
		return this._hoveredLine;
	}

	public setDraggingPoint(point: MeasurePointTarget | null): void {
		const changed =
			this._dragging?.id !== point?.id || this._dragging?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._dragging = point;
			this._dragChanged.fire(point);
		}
	}

	public getDraggingPoint(): MeasurePointTarget | null {
		return this._dragging;
	}

	public destroy(): void {
		this._drawingsChanged.destroy();
		this._drawingModeChanged.destroy();
		this._selectionChanged.destroy();
		this._hoverChanged.destroy();
		this._hoveredLineChanged.destroy();
		this._dragChanged.destroy();
	}
}
