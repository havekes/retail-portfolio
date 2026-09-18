import type { Time } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import type { DrawingPoint, MeasureDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import {
	computeMeasure,
	formatMeasureLabel,
	type MeasureDirection
} from '$lib/utils/finance/measure';
import { MouseHandlers, type ProjectedMeasurePointWithTarget } from './mouse';
import {
	type MeasurePreviewData,
	type MeasureRenderItem,
	type MeasureRendererData,
	type ProjectedMeasurePoint
} from './pane-renderer';
import { MeasurePaneView } from './pane-view';
import { MeasureToolState, type MeasurePointTarget } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';

export class MeasurePrimitive extends DrawingPrimitiveBase<
	MeasureRendererData,
	MeasurePaneView,
	MeasureToolState,
	MouseHandlers,
	MeasurePointTarget,
	MeasurePointTarget
> {
	constructor(initialState?: {
		measures?: MeasureDrawing[] | null;
		isDrawingMode?: boolean;
		selectedId?: string | null;
	}) {
		const state = new MeasureToolState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new MeasurePaneView();

		if (initialState?.measures) {
			state.setMeasures(initialState.measures);
		}
		if (initialState?.isDrawingMode !== undefined) {
			state.setDrawingMode(initialState.isDrawingMode);
		}
		if (initialState?.selectedId !== undefined) {
			state.select(initialState.selectedId);
		}

		super({
			externalId: 'measure-primitive',
			state,
			mouseHandlers,
			paneView
		});
	}

	protected override _setupSubscriptions(): void {
		this._subscribeToUpdate(this._state.drawingsChanged());
		this._subscribeToUpdate(this._state.selectionChanged());
		this._subscribeToUpdate(this._state.hoverChanged());
		this._subscribeToUpdate(this._state.dragChanged());

		this._subscribe(this._mouseHandlers.pointClicked(), (hit) => {
			this._state.select(hit.id);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.emptyAreaClicked(), () => {
			this._state.select(null);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(dragEvent.id, dragEvent.pointIndex, {
				time: dragEvent.time,
				price: dragEvent.price
			});
			this._requestUpdate?.();
		});
	}

	// --- Public API ---

	public getMeasures(): MeasureDrawing[] {
		return this._state.getMeasures();
	}

	public setMeasures(measures: MeasureDrawing[] | null | undefined): void {
		this._state.setMeasures(measures);
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

	public getHoveredPoint(): MeasurePointTarget | null {
		return this._state.getHoveredPoint();
	}

	public getDraggingPoint(): MeasurePointTarget | null {
		return this._state.getDraggingPoint();
	}

	public selectionChanged() {
		return this._state.selectionChanged();
	}

	public drawingsChanged() {
		return this._state.drawingsChanged();
	}

	public override setCandles(candles: Candle[]): void {
		super.setCandles(candles);
	}

	protected override _calculateRendererData(): MeasureRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const selectedId = this._state.getSelectedId();

		const measures: MeasureRenderItem[] = [];
		const projectedForMouse: ProjectedMeasurePointWithTarget[] = [];

		for (const drawing of this._state.getMeasures()) {
			if (drawing.visible === false) continue;
			const id = drawing.id;
			if (!id) continue;

			const x1 = this._timeProjector.epochToCoordinate(normalizeDrawingTime(drawing.p1.time));
			const y1 = series.priceToCoordinate(drawing.p1.price);
			const x2 = this._timeProjector.epochToCoordinate(normalizeDrawingTime(drawing.p2.time));
			const y2 = series.priceToCoordinate(drawing.p2.price);
			if (x1 === null || y1 === null || x2 === null || y2 === null) continue;

			const isSelected = selectedId === id;
			const p1: ProjectedMeasurePoint = {
				pointIndex: 0,
				x: x1,
				y: y1,
				time: drawing.p1.time,
				price: drawing.p1.price,
				isHovered: hovered?.id === id && hovered.pointIndex === 0,
				isDragging: dragging?.id === id && dragging.pointIndex === 0,
				isSelected
			};
			const p2: ProjectedMeasurePoint = {
				pointIndex: 1,
				x: x2,
				y: y2,
				time: drawing.p2.time,
				price: drawing.p2.price,
				isHovered: hovered?.id === id && hovered.pointIndex === 1,
				isDragging: dragging?.id === id && dragging.pointIndex === 1,
				isSelected
			};

			const { delta, percent, direction } = computeMeasure(drawing.p1, drawing.p2);
			measures.push({
				id,
				p1,
				p2,
				delta,
				percent,
				direction,
				label: formatMeasureLabel(delta, percent),
				visible: drawing.visible,
				isSelected
			});

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
		}

		this._mouseHandlers.setProjectedPoints(projectedForMouse);

		let preview: MeasurePreviewData | null = null;
		if (this._state.isDrawingMode()) {
			const pending = this._state.getPendingPoints();
			const placedPoints: ProjectedMeasurePoint[] = [];
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

			let label: string | null = null;
			let direction: MeasureDirection | null = null;
			if (pending.length === 1 && currentMouse && typeof currentMouse.price === 'number') {
				const anchor: DrawingPoint = {
					time: normalizeDrawingTime(pending[0].time),
					price: pending[0].price
				};
				const target: DrawingPoint = {
					time: normalizeDrawingTime(currentMouse.time ?? pending[0].time),
					price: currentMouse.price
				};
				const computation = computeMeasure(anchor, target);
				label = formatMeasureLabel(computation.delta, computation.percent);
				direction = computation.direction;
			}

			preview = { placedPoints, currentMouse, label, direction };
		}

		return { measures, preview };
	}
}
