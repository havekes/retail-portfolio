import type { DrawingPoint, HorizontalLineDrawing } from '$lib/utils/finance/drawings';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';
import { MouseHandlers, type ProjectedHorizontalLinePointWithTarget } from './mouse';
import {
	type HorizontalPreviewData,
	type HorizontalRenderItem,
	type HorizontalRendererData,
	type ProjectedHorizontalLinePoint
} from './pane-renderer';
import { HorizontalLinePaneView } from './pane-view';
import { HorizontalLineToolState, type HorizontalLineTarget } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';

/**
 * Horizontal line drawing primitive. A single click on the chart commits a line
 * at the clicked price; dragging its handle changes only the price so the line
 * stays horizontal and anchored at its original time.
 */
export class HorizontalLinePrimitive extends DrawingPrimitiveBase<
	HorizontalRendererData,
	HorizontalLinePaneView,
	HorizontalLineToolState,
	MouseHandlers,
	HorizontalLineTarget,
	HorizontalLineTarget
> {
	private _hideLabels: boolean = false;

	constructor(initialState?: {
		horizontalLines?: HorizontalLineDrawing[] | null;
		isDrawingMode?: boolean;
		selectedId?: string | null;
		hideLabels?: boolean;
	}) {
		const state = new HorizontalLineToolState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new HorizontalLinePaneView();

		if (initialState?.horizontalLines) {
			state.setHorizontalLines(initialState.horizontalLines);
		}
		if (initialState?.isDrawingMode !== undefined) {
			state.setDrawingMode(initialState.isDrawingMode);
		}
		if (initialState?.selectedId !== undefined) {
			state.select(initialState.selectedId);
		}

		super({
			externalId: 'horizontal-line-primitive',
			state,
			mouseHandlers,
			paneView
		});

		this._hideLabels = initialState?.hideLabels ?? false;
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

		// Drags move the price only: the anchor time is intentionally dropped so
		// the line remains horizontal and epoch-anchored at its placement time.
		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(dragEvent.id, { price: dragEvent.price });
			this._requestUpdate?.();
		});
	}

	// --- Public API ---

	public getHorizontalLines(): HorizontalLineDrawing[] {
		return this._state.getHorizontalLines();
	}

	public setHorizontalLines(lines: HorizontalLineDrawing[] | null | undefined): void {
		this._state.setHorizontalLines(lines);
	}

	public addPoint(point: DrawingPoint): DrawingPoint {
		return this._state.addPoint(point);
	}

	public updatePoint(id: string, update: { price?: number }): boolean {
		return this._state.updatePoint(id, update);
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

	public getHoveredPoint(): HorizontalLineTarget | null {
		return this._state.getHoveredPoint();
	}

	public getDraggingPoint(): HorizontalLineTarget | null {
		return this._state.getDraggingPoint();
	}

	public selectionChanged() {
		return this._state.selectionChanged();
	}

	public drawingsChanged() {
		return this._state.drawingsChanged();
	}

	/** Toggles the price label on every line (wired to the chart hide-labels pref). */
	public setHideLabels(hideLabels: boolean): void {
		if (this._hideLabels === hideLabels) return;
		this._hideLabels = hideLabels;
		this._requestUpdate?.();
	}

	protected override _calculateRendererData(): HorizontalRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const selectedId = this._state.getSelectedId();

		const formatter = series.priceFormatter?.();
		const formatPrice = (price: number): string =>
			formatter ? formatter.format(price) : price.toFixed(2);

		const lines: HorizontalRenderItem[] = [];
		const projectedForMouse: ProjectedHorizontalLinePointWithTarget[] = [];

		for (const drawing of this._state.getHorizontalLines()) {
			if (drawing.visible === false) continue;
			const id = drawing.id;
			if (!id) continue;

			const x = this._timeProjector.epochToCoordinate(normalizeDrawingTime(drawing.p1.time));
			const y = series.priceToCoordinate(drawing.p1.price);
			if (x === null || y === null) continue;

			const isSelected = selectedId === id;
			const p1: ProjectedHorizontalLinePoint = {
				x,
				y,
				time: drawing.p1.time,
				price: drawing.p1.price,
				isHovered: hovered?.id === id,
				isDragging: dragging?.id === id,
				isSelected
			};

			lines.push({
				id,
				p1,
				label: formatPrice(drawing.p1.price),
				showLabel: !this._hideLabels,
				visible: drawing.visible,
				isSelected
			});

			projectedForMouse.push({
				id,
				x,
				y,
				originalPoint: drawing.p1
			});
		}

		this._mouseHandlers.setProjectedPoints(projectedForMouse);

		let preview: HorizontalPreviewData | null = null;
		if (this._state.isDrawingMode()) {
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

			preview = {
				currentMouse,
				label:
					currentMouse && typeof currentMouse.price === 'number'
						? formatPrice(currentMouse.price)
						: null,
				showLabel: !this._hideLabels
			};
		}

		return { lines, preview };
	}
}
