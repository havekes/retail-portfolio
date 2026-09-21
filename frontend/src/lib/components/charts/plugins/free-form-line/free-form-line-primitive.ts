import type { Time } from 'lightweight-charts';
import type { DrawingPoint, LineDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import {
	MouseHandlers,
	type ProjectedLinePointWithTarget,
	type ProjectedLineSegment
} from './mouse';
import {
	type LinePreviewData,
	type LineRenderItem,
	type LineRendererData,
	type ProjectedLinePoint
} from './pane-renderer';
import { LinePaneView } from './pane-view';
import { LineToolState, type LinePointTarget } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';

/**
 * Free-form line drawing primitive. Two clicks place a straight segment between
 * arbitrary chart points; either endpoint can be dragged in both time and price
 * (unlike the horizontal line, whose drag is price-only).
 */
export class FreeFormLinePrimitive extends DrawingPrimitiveBase<
	LineRendererData,
	LinePaneView,
	LineToolState,
	MouseHandlers,
	LinePointTarget,
	LinePointTarget
> {
	constructor(initialState?: {
		lines?: LineDrawing[] | null;
		isDrawingMode?: boolean;
		selectedId?: string | null;
	}) {
		const state = new LineToolState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new LinePaneView();

		if (initialState?.lines) {
			state.setLines(initialState.lines);
		}
		if (initialState?.isDrawingMode !== undefined) {
			state.setDrawingMode(initialState.isDrawingMode);
		}
		if (initialState?.selectedId !== undefined) {
			state.select(initialState.selectedId);
		}

		super({
			externalId: 'free-form-line-primitive',
			state,
			mouseHandlers,
			paneView
		});
	}

	protected override _setupSubscriptions(): void {
		this._subscribeToUpdate(this._state.drawingsChanged());
		this._subscribeToUpdate(this._state.selectionChanged());
		this._subscribeToUpdate(this._state.hoverChanged());
		this._subscribeToUpdate(this._state.hoveredLineChanged());
		this._subscribeToUpdate(this._state.dragChanged());

		this._subscribe(this._mouseHandlers.pointClicked(), (hit) => {
			this._state.select(hit.id);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.lineClicked(), (hit) => {
			this._state.select(hit.id);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.lineHovered(), (hit) => {
			this._state.setHoveredLine(hit);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.emptyAreaClicked(), () => {
			this._state.select(null);
			this._requestUpdate?.();
		});

		// Both endpoints drag freely in time and price.
		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(dragEvent.id, dragEvent.pointIndex, {
				time: dragEvent.time,
				price: dragEvent.price
			});
			this._requestUpdate?.();
		});
	}

	// --- Public API ---

	public getLines(): LineDrawing[] {
		return this._state.getLines();
	}

	public setLines(lines: LineDrawing[] | null | undefined): void {
		this._state.setLines(lines);
	}

	public addPoint(point: DrawingPoint): DrawingPoint {
		return this._state.addPoint(point);
	}

	public updatePoint(
		id: string,
		pointIndex: 0 | 1,
		update: { time?: Time; price?: number }
	): boolean {
		return this._state.updatePoint(id, pointIndex, update);
	}

	public removeDrawing(id: string): boolean {
		return this._state.removeDrawing(id);
	}

	public select(id: string | null): void {
		this._state.select(id);
	}

	public getSelectedId(): string | null {
		return this._state.getSelectedId();
	}

	public setSelectedId(id: string | null): void {
		this._state.select(id);
	}

	public getHoveredPoint(): LinePointTarget | null {
		return this._state.getHoveredPoint();
	}

	public getHoveredLine(): LinePointTarget | null {
		return this._state.getHoveredLine();
	}

	public getDraggingPoint(): LinePointTarget | null {
		return this._state.getDraggingPoint();
	}

	public selectionChanged() {
		return this._state.selectionChanged();
	}

	public drawingsChanged() {
		return this._state.drawingsChanged();
	}

	protected override _calculateRendererData(): LineRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const hovered = this._state.getHoveredPoint();
		const hoveredLine = this._state.getHoveredLine();
		const dragging = this._state.getDraggingPoint();
		const selectedId = this._state.getSelectedId();

		const lines: LineRenderItem[] = [];
		const projectedForMouse: ProjectedLinePointWithTarget[] = [];
		const projectedLines: ProjectedLineSegment[] = [];

		for (const drawing of this._state.getLines()) {
			if (drawing.visible === false) continue;
			const id = drawing.id;
			if (!id) continue;

			const x1 = this._timeProjector.epochToCoordinate(normalizeDrawingTime(drawing.p1.time));
			const y1 = series.priceToCoordinate(drawing.p1.price);
			const x2 = this._timeProjector.epochToCoordinate(normalizeDrawingTime(drawing.p2.time));
			const y2 = series.priceToCoordinate(drawing.p2.price);
			if (x1 === null || y1 === null || x2 === null || y2 === null) continue;

			const isSelected = selectedId === id;
			const isHovered = hoveredLine?.id === id;
			const p1: ProjectedLinePoint = {
				pointIndex: 0,
				x: x1,
				y: y1,
				time: drawing.p1.time,
				price: drawing.p1.price,
				isHovered: hovered?.id === id && hovered.pointIndex === 0,
				isDragging: dragging?.id === id && dragging.pointIndex === 0,
				isSelected
			};
			const p2: ProjectedLinePoint = {
				pointIndex: 1,
				x: x2,
				y: y2,
				time: drawing.p2.time,
				price: drawing.p2.price,
				isHovered: hovered?.id === id && hovered.pointIndex === 1,
				isDragging: dragging?.id === id && dragging.pointIndex === 1,
				isSelected
			};

			lines.push({ id, p1, p2, visible: drawing.visible, isSelected, isHovered });

			projectedForMouse.push({
				id,
				pointIndex: 0,
				x: x1,
				y: y1,
				originalPoint: drawing.p1
			});
			projectedForMouse.push({
				id,
				pointIndex: 1,
				x: x2,
				y: y2,
				originalPoint: drawing.p2
			});

			projectedLines.push({
				id,
				p1: { x: x1, y: y1 },
				p2: { x: x2, y: y2 }
			});
		}

		this._mouseHandlers.setProjectedPoints(projectedForMouse);
		this._mouseHandlers.setProjectedLines(projectedLines);

		let preview: LinePreviewData | null = null;
		if (this._state.isDrawingMode()) {
			const pending = this._state.getPendingPoints();
			const placedPoints: ProjectedLinePoint[] = [];
			for (let i = 0; i < pending.length; i++) {
				const pt = pending[i];
				const x = this._timeProjector.epochToCoordinate(normalizeDrawingTime(pt.time));
				const y = series.priceToCoordinate(pt.price);
				if (x !== null && y !== null) {
					placedPoints.push({
						pointIndex: i as 0 | 1,
						x,
						y,
						time: pt.time,
						price: pt.price
					});
				}
			}

			const lastMouse = this._mouseHandlers.getLastMousePosition();
			const currentMouse =
				lastMouse && lastMouse.insidePlotArea
					? {
							x: lastMouse.x,
							y: lastMouse.y,
							time: lastMouse.time,
							price: lastMouse.price
						}
					: null;

			preview = { placedPoints, currentMouse };
		}

		return { lines, preview };
	}
}
