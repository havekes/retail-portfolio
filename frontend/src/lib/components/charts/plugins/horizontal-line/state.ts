import { Delegate, type ISubscription } from '../helpers/delegate';
import type { DrawingPoint, HorizontalLineDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { generateUUID } from '$lib/utils/finance/rewind';

/** Identifies the single draggable handle of a horizontal line drawing. */
export interface HorizontalLineTarget {
	id: string;
}

function normalizeDrawingPoint(point: DrawingPoint): DrawingPoint {
	return { time: normalizeDrawingTime(point.time), price: point.price };
}

function normalizeLine(
	drawing: HorizontalLineDrawing,
	idFactory: () => string
): HorizontalLineDrawing {
	return {
		id: drawing.id ?? idFactory(),
		p1: normalizeDrawingPoint(drawing.p1),
		visible: drawing.visible
	};
}

/**
 * State for the Horizontal Line tool. Unlike Measure (two anchors), a single
 * click is enough to complete a line, so `addPoint` commits immediately and
 * exits drawing mode. Selection/hover/drag are keyed by drawing id only; there
 * is no point index. Anchors are canonicalized to epoch seconds on ingestion so
 * drawings are timeframe-independent, and the anchor time is never mutated by
 * drags — dragging only moves the price, keeping the line horizontal.
 */
export class HorizontalLineToolState {
	private _lines: HorizontalLineDrawing[] = [];
	private _selectedId: string | null = null;
	private _hovered: HorizontalLineTarget | null = null;
	private _hoveredLine: HorizontalLineTarget | null = null;
	private _dragging: HorizontalLineTarget | null = null;
	private _isDrawingMode: boolean = false;

	private readonly _idFactory: () => string;

	private _drawingsChanged: Delegate<HorizontalLineDrawing[]> = new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _selectionChanged: Delegate<string | null> = new Delegate();
	private _hoverChanged: Delegate<HorizontalLineTarget | null> = new Delegate();
	private _hoveredLineChanged: Delegate<HorizontalLineTarget | null> = new Delegate();
	private _dragChanged: Delegate<HorizontalLineTarget | null> = new Delegate();

	constructor(idFactory: () => string = generateUUID) {
		this._idFactory = idFactory;
	}

	public drawingsChanged(): ISubscription<HorizontalLineDrawing[]> {
		return this._drawingsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public selectionChanged(): ISubscription<string | null> {
		return this._selectionChanged;
	}

	public hoverChanged(): ISubscription<HorizontalLineTarget | null> {
		return this._hoverChanged;
	}

	public hoveredLineChanged(): ISubscription<HorizontalLineTarget | null> {
		return this._hoveredLineChanged;
	}

	public dragChanged(): ISubscription<HorizontalLineTarget | null> {
		return this._dragChanged;
	}

	public getHorizontalLines(): HorizontalLineDrawing[] {
		return this._lines.map((line) => ({
			...line,
			p1: { ...line.p1 }
		}));
	}

	/** Replaces the whole collection, normalizing anchors and ensuring ids. */
	public setHorizontalLines(lines: HorizontalLineDrawing[] | null | undefined): void {
		const next = (lines ?? []).map((line) => normalizeLine(line, this._idFactory));
		this._lines = next;
		if (this._selectedId !== null && !next.some((line) => line.id === this._selectedId)) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		this._drawingsChanged.fire(this.getHorizontalLines());
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
		this._drawingModeChanged.fire(enabled);
	}

	public cancelDrawing(): void {
		this.setDrawingMode(false);
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

		this._lines = [...this._lines, { id: this._idFactory(), p1: newPoint, visible: true }];
		this.setDrawingMode(false);
		this._drawingsChanged.fire(this.getHorizontalLines());
		return newPoint;
	}

	/** Updates the line's price only; the anchor time never moves (stays horizontal). */
	public updatePoint(id: string, update: { price?: number }): boolean {
		const index = this._lines.findIndex((line) => line.id === id);
		if (index < 0) return false;
		const current = this._lines[index];
		if (update.price === undefined) return false;
		const p1 = { ...current.p1, price: update.price };
		const next = [...this._lines];
		next[index] = { ...current, p1 };
		this._lines = next;
		this._drawingsChanged.fire(this.getHorizontalLines());
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
		if (this._hoveredLine?.id === id) this.setHoveredLine(null);
		if (this._dragging?.id === id) this.setDraggingPoint(null);
		this._drawingsChanged.fire(this.getHorizontalLines());
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

	public setHoveredPoint(target: HorizontalLineTarget | null): void {
		const changed = this._hovered?.id !== target?.id;
		if (changed) {
			this._hovered = target;
			this._hoverChanged.fire(target);
		}
	}

	public getHoveredPoint(): HorizontalLineTarget | null {
		return this._hovered;
	}

	public setHoveredLine(target: HorizontalLineTarget | null): void {
		const changed = this._hoveredLine?.id !== target?.id;
		if (changed) {
			this._hoveredLine = target;
			this._hoveredLineChanged.fire(target);
		}
	}

	public getHoveredLine(): HorizontalLineTarget | null {
		return this._hoveredLine;
	}

	public setDraggingPoint(target: HorizontalLineTarget | null): void {
		const changed = this._dragging?.id !== target?.id;
		if (changed) {
			this._dragging = target;
			this._dragChanged.fire(target);
		}
	}

	public getDraggingPoint(): HorizontalLineTarget | null {
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
