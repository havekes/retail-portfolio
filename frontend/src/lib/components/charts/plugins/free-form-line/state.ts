import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import type { DrawingPoint, LineDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies one draggable endpoint of a free-form line drawing. */
export interface LinePointTarget {
	id: string;
	pointIndex: 0 | 1;
}

function normalizeDrawingPoint(point: DrawingPoint): DrawingPoint {
	return { time: normalizeDrawingTime(point.time), price: point.price };
}

function normalizeLine(drawing: LineDrawing, idFactory: () => string): LineDrawing {
	return {
		id: drawing.id ?? idFactory(),
		p1: normalizeDrawingPoint(drawing.p1),
		p2: normalizeDrawingPoint(drawing.p2),
		visible: drawing.visible
	};
}

/**
 * State for the free-form line tool. Owns a collection of two-point drawings
 * (unlike Fibonacci/Measure's single drawing or horizontal line's single
 * anchor); selection/hover/drag are keyed by drawing id + endpoint index.
 * Anchors are canonicalized to epoch seconds on ingestion so drawings are
 * timeframe-independent, and both endpoints are freely draggable in time and
 * price (the segment is not constrained to be horizontal).
 */
export class LineToolState {
	private _lines: LineDrawing[] = [];
	private _pendingPoints: DrawingPoint[] = [];
	private _selectedId: string | null = null;
	private _hovered: LinePointTarget | null = null;
	private _dragging: LinePointTarget | null = null;
	private _isDrawingMode: boolean = false;

	private readonly _idFactory: () => string;

	private _drawingsChanged: Delegate<LineDrawing[]> = new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _selectionChanged: Delegate<string | null> = new Delegate();
	private _hoverChanged: Delegate<LinePointTarget | null> = new Delegate();
	private _dragChanged: Delegate<LinePointTarget | null> = new Delegate();

	constructor(idFactory: () => string = generateUUID) {
		this._idFactory = idFactory;
	}

	public drawingsChanged(): ISubscription<LineDrawing[]> {
		return this._drawingsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public selectionChanged(): ISubscription<string | null> {
		return this._selectionChanged;
	}

	public hoverChanged(): ISubscription<LinePointTarget | null> {
		return this._hoverChanged;
	}

	public dragChanged(): ISubscription<LinePointTarget | null> {
		return this._dragChanged;
	}

	public getLines(): LineDrawing[] {
		return this._lines.map((line) => ({
			...line,
			p1: { ...line.p1 },
			p2: { ...line.p2 }
		}));
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setLines(lines: LineDrawing[] | null | undefined): void {
		const next = (lines ?? []).map((line) => normalizeLine(line, this._idFactory));
		this._lines = next;
		if (this._selectedId !== null && !next.some((line) => line.id === this._selectedId)) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		this._drawingsChanged.fire(this.getLines());
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
				this._drawingsChanged.fire(this.getLines());
			}
		}
		this._drawingModeChanged.fire(enabled);
	}

	public cancelDrawing(): void {
		const hadPending = this._pendingPoints.length > 0;
		this._pendingPoints = [];
		if (hadPending) {
			this._drawingsChanged.fire(this.getLines());
		}
		this.setDrawingMode(false);
	}

	/**
	 * Adds an anchor for the current (in-progress) drawing. The second point
	 * completes a line with a freshly generated id and exits drawing mode.
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
			this._lines = [...this._lines, { id: this._idFactory(), p1, p2, visible: true }];
			this._pendingPoints = [];
			this.setDrawingMode(false);
		}
		this._drawingsChanged.fire(this.getLines());
		return newPoint;
	}

	public updatePoint(
		id: string,
		pointIndex: 0 | 1,
		update: { time?: Time; price?: number }
	): boolean {
		const index = this._lines.findIndex((line) => line.id === id);
		if (index < 0) return false;
		const current = this._lines[index];
		const p1 = { ...current.p1 };
		const p2 = { ...current.p2 };
		if (pointIndex === 0) {
			if (update.time !== undefined) p1.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p1.price = update.price;
		} else {
			if (update.time !== undefined) p2.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p2.price = update.price;
		}
		const next = [...this._lines];
		next[index] = { ...current, p1, p2 };
		this._lines = next;
		this._drawingsChanged.fire(this.getLines());
		return true;
	}

	public removeDrawing(id: string): boolean {
		const next = this._lines.filter((line) => line.id !== id);
		if (next.length === this._lines.length) return false;
		this._lines = next;
		if (this._selectedId === id) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		if (this._hovered?.id === id) this.setHoveredPoint(null);
		if (this._dragging?.id === id) this.setDraggingPoint(null);
		this._drawingsChanged.fire(this.getLines());
		return true;
	}

	public getSelectedId(): string | null {
		return this._selectedId;
	}

	public select(id: string | null): void {
		if (id !== null && !this._lines.some((line) => line.id === id)) return;
		if (this._selectedId !== id) {
			this._selectedId = id;
			this._selectionChanged.fire(id);
		}
	}

	public setHoveredPoint(point: LinePointTarget | null): void {
		const changed =
			this._hovered?.id !== point?.id || this._hovered?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._hovered = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): LinePointTarget | null {
		return this._hovered;
	}

	public setDraggingPoint(point: LinePointTarget | null): void {
		const changed =
			this._dragging?.id !== point?.id || this._dragging?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._dragging = point;
			this._dragChanged.fire(point);
		}
	}

	public getDraggingPoint(): LinePointTarget | null {
		return this._dragging;
	}

	public destroy(): void {
		this._drawingsChanged.destroy();
		this._drawingModeChanged.destroy();
		this._selectionChanged.destroy();
		this._hoverChanged.destroy();
		this._dragChanged.destroy();
	}
}
