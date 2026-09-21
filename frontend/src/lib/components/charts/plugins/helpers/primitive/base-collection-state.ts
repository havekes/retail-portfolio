import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../delegate';
import type { IDrawingToolState } from './drawing-primitive-base';
import {
	areDrawingCollectionsEqual,
	type Drawing,
	type DrawingPoint
} from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { generateUUID } from '$lib/utils/finance/rewind';

/**
 * Abstract base class managing multi-drawing collection state for chart drawing tools.
 *
 * Encapsulates drawing collection storage, ID generation and anchor time normalization,
 * reactive loop prevention on external updates, selection, hover/drag targeting,
 * drawing mode lifecycle, and delegate event firing.
 */
export abstract class BaseCollectionToolState<
	TDrawing extends { id?: string },
	TTarget extends { id: string } = { id: string }
> implements IDrawingToolState<TTarget, TTarget> {
	protected _drawings: TDrawing[] = [];
	protected _pendingPoints: DrawingPoint[] = [];
	protected _selectedId: string | null = null;
	protected _hovered: TTarget | null = null;
	protected _hoveredLine: TTarget | null = null;
	protected _dragging: TTarget | null = null;
	protected _isDrawingMode: boolean = false;

	protected readonly _idFactory: () => string;

	protected readonly _drawingsChanged: Delegate<TDrawing[]> = new Delegate();
	protected readonly _drawingModeChanged: Delegate<boolean> = new Delegate();
	protected readonly _selectionChanged: Delegate<string | null> = new Delegate();
	protected readonly _hoverChanged: Delegate<TTarget | null> = new Delegate();
	protected readonly _hoveredLineChanged: Delegate<TTarget | null> = new Delegate();
	protected readonly _dragChanged: Delegate<TTarget | null> = new Delegate();

	constructor(idFactory: () => string = generateUUID) {
		this._idFactory = idFactory;
	}

	public drawingsChanged(): ISubscription<TDrawing[]> {
		return this._drawingsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public selectionChanged(): ISubscription<string | null> {
		return this._selectionChanged;
	}

	public hoverChanged(): ISubscription<TTarget | null> {
		return this._hoverChanged;
	}

	public hoveredLineChanged(): ISubscription<TTarget | null> {
		return this._hoveredLineChanged;
	}

	public dragChanged(): ISubscription<TTarget | null> {
		return this._dragChanged;
	}

	protected _normalizePoint(point: DrawingPoint): DrawingPoint {
		return {
			time: normalizeDrawingTime(point.time),
			price: point.price
		};
	}

	protected _normalizeDrawing(drawing: TDrawing): TDrawing {
		const d = drawing as Record<string, unknown>;
		const normalized: Record<string, unknown> = {
			...d,
			id: drawing.id ?? this._idFactory()
		};
		if (d.p1 && typeof d.p1 === 'object') {
			normalized.p1 = this._normalizePoint(d.p1 as DrawingPoint);
		}
		if (d.p2 && typeof d.p2 === 'object') {
			normalized.p2 = this._normalizePoint(d.p2 as DrawingPoint);
		}
		return normalized as TDrawing;
	}

	protected _cloneDrawing(drawing: TDrawing): TDrawing {
		const d = drawing as Record<string, unknown>;
		const copy: Record<string, unknown> = { ...d };
		if (d.p1 && typeof d.p1 === 'object') {
			copy.p1 = { ...(d.p1 as object) };
		}
		if (d.p2 && typeof d.p2 === 'object') {
			copy.p2 = { ...(d.p2 as object) };
		}
		return copy as TDrawing;
	}

	protected _areDrawingsEqual(a: TDrawing[], b: TDrawing[]): boolean {
		return areDrawingCollectionsEqual(a as unknown as Drawing[], b as unknown as Drawing[]);
	}

	public getDrawings(): TDrawing[] {
		return this._drawings.map((d) => this._cloneDrawing(d));
	}

	/**
	 * Replaces the drawing collection, normalizing anchor times and assigning IDs.
	 * Compares normalized incoming drawings against existing drawings to prevent
	 * redundant event firing and reactive feedback loops.
	 */
	public setDrawings(drawings: TDrawing[] | null | undefined): void {
		const next = (drawings ?? []).map((d) => this._normalizeDrawing(d));
		if (this._areDrawingsEqual(this._drawings, next)) {
			return;
		}
		this._drawings = next;
		if (this._selectedId !== null && !next.some((d) => d.id === this._selectedId)) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		this._drawingsChanged.fire(this.getDrawings());
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
				this._drawingsChanged.fire(this.getDrawings());
			}
		}
		this._drawingModeChanged.fire(enabled);
	}

	public cancelDrawing(): void {
		const hadPending = this._pendingPoints.length > 0;
		this._pendingPoints = [];
		if (hadPending) {
			this._drawingsChanged.fire(this.getDrawings());
		}
		this.setDrawingMode(false);
	}

	public abstract addPoint(point: DrawingPoint): DrawingPoint;

	protected _addTwoPointDrawing(point: DrawingPoint): DrawingPoint {
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
			const drawing = { id: this._idFactory(), p1, p2, visible: true } as unknown as TDrawing;
			this._drawings = [...this._drawings, drawing];
			this._pendingPoints = [];
			this.setDrawingMode(false);
		}
		this._drawingsChanged.fire(this.getDrawings());
		return newPoint;
	}

	protected _updateTwoPointDrawing(
		id: string,
		pointIndex: 0 | 1,
		update: { time?: Time; price?: number }
	): boolean {
		const index = this._drawings.findIndex((d) => d.id === id);
		if (index < 0) return false;
		const current = this._drawings[index] as unknown as {
			id: string;
			p1: DrawingPoint;
			p2: DrawingPoint;
			visible?: boolean;
		};
		const p1 = { ...current.p1 };
		const p2 = { ...current.p2 };
		if (pointIndex === 0) {
			if (update.time !== undefined) p1.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p1.price = update.price;
		} else {
			if (update.time !== undefined) p2.time = normalizeDrawingTime(update.time);
			if (update.price !== undefined) p2.price = update.price;
		}
		const next = [...this._drawings];
		next[index] = { ...current, p1, p2 } as unknown as TDrawing;
		this._drawings = next;
		this._drawingsChanged.fire(this.getDrawings());
		return true;
	}

	public removeDrawing(id: string): boolean {
		const next = this._drawings.filter((d) => d.id !== id);
		if (next.length === this._drawings.length) return false;
		this._drawings = next;
		if (this._selectedId === id) {
			this._selectedId = null;
			this._selectionChanged.fire(null);
		}
		if (this._hovered?.id === id) this.setHoveredPoint(null);
		if (this._hoveredLine?.id === id) this.setHoveredLine(null);
		if (this._dragging?.id === id) this.setDraggingPoint(null);
		this._drawingsChanged.fire(this.getDrawings());
		return true;
	}

	public getSelectedId(): string | null {
		return this._selectedId;
	}

	public select(id: string | null): void {
		if (id !== null && !this._drawings.some((d) => d.id === id)) return;
		if (this._selectedId !== id) {
			this._selectedId = id;
			this._selectionChanged.fire(id);
		}
	}

	protected _targetsEqual(a: TTarget | null, b: TTarget | null): boolean {
		if (a === b) return true;
		if (!a || !b) return false;
		if (a.id !== b.id) return false;
		const aPointIndex = 'pointIndex' in a ? (a as { pointIndex?: unknown }).pointIndex : undefined;
		const bPointIndex = 'pointIndex' in b ? (b as { pointIndex?: unknown }).pointIndex : undefined;
		return aPointIndex === bPointIndex;
	}

	public setHoveredPoint(point: TTarget | null): void {
		if (!this._targetsEqual(this._hovered, point)) {
			this._hovered = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): TTarget | null {
		return this._hovered;
	}

	public setHoveredLine(line: TTarget | null): void {
		const changed = this._hoveredLine?.id !== line?.id;
		if (changed) {
			this._hoveredLine = line;
			this._hoveredLineChanged.fire(line);
		}
	}

	public getHoveredLine(): TTarget | null {
		return this._hoveredLine;
	}

	public setDraggingPoint(point: TTarget | null): void {
		if (!this._targetsEqual(this._dragging, point)) {
			this._dragging = point;
			this._dragChanged.fire(point);
		}
	}

	public getDraggingPoint(): TTarget | null {
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
