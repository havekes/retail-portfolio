import type { ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import type { ISubscription } from '../helpers/delegate';
import {
	calculateExtensionLevels,
	calculateRetracementLevels,
	type FibComputedLevel,
	type FibExtensionDrawing,
	type FibPoint,
	type FibRetracementDrawing,
	type FibToolType,
	type SecurityFibonacciTools
} from '$lib/utils/finance/fibonacci';
import { MouseHandlers, type ProjectedFibPointWithTarget } from './mouse';
import {
	type ExtensionRenderData,
	type FibDrawingPreviewData,
	type FibonacciRendererData,
	type ProjectedFibLevel,
	type ProjectedFibPoint,
	type RetracementRenderData
} from './pane-renderer';
import { FibonacciPaneView } from './pane-view';
import { FibonacciToolState, type FibPointTarget } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';

function projectLevels(
	computedLevels: FibComputedLevel[],
	series: ISeriesApi<SeriesType>
): ProjectedFibLevel[] {
	const projectedLevels: ProjectedFibLevel[] = [];
	for (const lvl of computedLevels) {
		const y = series.priceToCoordinate(lvl.price);
		if (y !== null) {
			projectedLevels.push({
				ratio: lvl.ratio,
				price: lvl.price,
				y,
				formattedPrice: lvl.formattedPrice,
				label: lvl.label,
				color: lvl.color,
				enabled: lvl.enabled
			});
		}
	}
	return projectedLevels;
}

export class FibonacciPrimitive extends DrawingPrimitiveBase<
	FibonacciRendererData,
	FibonacciPaneView,
	FibonacciToolState,
	MouseHandlers,
	FibPointTarget,
	FibPointTarget
> {
	constructor(initialState?: {
		activeTool?: FibToolType | null;
		drawings?: SecurityFibonacciTools;
		isDrawingMode?: boolean;
		selectedTool?: FibToolType | null;
	}) {
		const state = new FibonacciToolState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new FibonacciPaneView();

		if (initialState?.activeTool !== undefined) {
			state.setActiveTool(initialState.activeTool);
		}
		if (initialState?.drawings) {
			state.setDrawings(initialState.drawings);
		}
		if (initialState?.isDrawingMode !== undefined) {
			state.setDrawingMode(initialState.isDrawingMode);
		}
		if (initialState?.selectedTool !== undefined) {
			state.setSelectedTool(initialState.selectedTool);
		}

		super({
			externalId: 'fibonacci-primitive',
			state,
			mouseHandlers,
			paneView
		});
	}

	protected override _setupSubscriptions(): void {
		this._subscribeToUpdate(this._state.drawingsChanged());
		this._subscribeToUpdate(this._state.toolChanged());
		this._subscribeToUpdate(this._state.selectionChanged());
		this._subscribeToUpdate(this._state.hoverChanged());
		this._subscribeToUpdate(this._state.dragChanged());

		this._subscribe(this._mouseHandlers.pointClicked(), (hit) => {
			this._state.setSelectedTool(hit.tool);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.emptyAreaClicked(), () => {
			this._state.setSelectedTool(null);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(dragEvent.tool, dragEvent.pointIndex, {
				time: dragEvent.time,
				price: dragEvent.price
			});
			this._requestUpdate?.();
		});
	}

	// State and Public API Accessors
	public getActiveTool(): FibToolType | null {
		return this._state.getActiveTool();
	}

	public setActiveTool(tool: FibToolType | null): void {
		this._state.setActiveTool(tool);
	}

	public getRetracement(): FibRetracementDrawing | null {
		return this._state.getRetracement();
	}

	public setRetracement(drawing: FibRetracementDrawing | null): void {
		this._state.setRetracement(drawing);
	}

	public getExtension(): FibExtensionDrawing | null {
		return this._state.getExtension();
	}

	public setExtension(drawing: FibExtensionDrawing | null): void {
		this._state.setExtension(drawing);
	}

	public getDrawings(): SecurityFibonacciTools {
		return this._state.getDrawings();
	}

	public setDrawings(tools: SecurityFibonacciTools): void {
		this._state.setDrawings(tools);
	}

	public getPendingPoints(): FibPoint[] {
		return this._state.getPendingPoints();
	}

	public addPoint(point: FibPoint, tool?: FibToolType): FibPoint {
		return this._state.addPoint(point, tool);
	}

	public updatePoint(
		tool: FibToolType,
		pointIndex: 0 | 1 | 2 | number,
		update: { time?: Time; price?: number }
	): boolean {
		return this._state.updatePoint(tool, pointIndex, update);
	}

	public clear(tool?: FibToolType): void {
		this._state.clear(tool);
	}

	public getSelectedTool(): FibToolType | null {
		return this._state.getSelectedTool();
	}

	public setSelectedTool(tool: FibToolType | null): void {
		this._state.setSelectedTool(tool);
	}

	public selectionChanged(): ISubscription<FibToolType | null> {
		return this._state.selectionChanged();
	}

	public getHoveredPoint(): FibPointTarget | null {
		return this._state.getHoveredPoint();
	}

	public getDraggingPoint(): FibPointTarget | null {
		return this._state.getDraggingPoint();
	}

	public drawingsChanged(): ISubscription<SecurityFibonacciTools> {
		return this._state.drawingsChanged();
	}

	public toolChanged(): ISubscription<FibToolType | null> {
		return this._state.toolChanged();
	}

	public hoverChanged(): ISubscription<FibPointTarget | null> {
		return this._state.hoverChanged();
	}

	public dragChanged(): ISubscription<FibPointTarget | null> {
		return this._state.dragChanged();
	}

	public setCandles(candles: Candle[]): void {
		this._mouseHandlers.setCandles(candles);
	}

	protected override _calculateRendererData(): FibonacciRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const allProjectedPointsForMouse: ProjectedFibPointWithTarget[] = [];
		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const selectedTool = this._state.getSelectedTool();
		const isRetracementSelected = selectedTool === 'retracement';
		const isExtensionSelected = selectedTool === 'extension';

		// 1. Retracement calculation
		let retracementRenderData: RetracementRenderData | null = null;
		const retracement = this._state.getRetracement();

		if (retracement && retracement.visible !== false) {
			const x1 = this._timeProjector.timeToCoordinate(retracement.p1.time);
			const y1 = series.priceToCoordinate(retracement.p1.price);
			const x2 = this._timeProjector.timeToCoordinate(retracement.p2.time);
			const y2 = series.priceToCoordinate(retracement.p2.price);

			if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) {
				const isP1Hovered = hovered?.tool === 'retracement' && hovered?.pointIndex === 0;
				const isP1Dragging = dragging?.tool === 'retracement' && dragging?.pointIndex === 0;
				const isP2Hovered = hovered?.tool === 'retracement' && hovered?.pointIndex === 1;
				const isP2Dragging = dragging?.tool === 'retracement' && dragging?.pointIndex === 1;

				const p1Projected: ProjectedFibPoint = {
					pointIndex: 0,
					x: x1,
					y: y1,
					time: retracement.p1.time,
					price: retracement.p1.price,
					isHovered: isP1Hovered,
					isDragging: isP1Dragging,
					isSelected: isRetracementSelected
				};

				const p2Projected: ProjectedFibPoint = {
					pointIndex: 1,
					x: x2,
					y: y2,
					time: retracement.p2.time,
					price: retracement.p2.price,
					isHovered: isP2Hovered,
					isDragging: isP2Dragging,
					isSelected: isRetracementSelected
				};

				allProjectedPointsForMouse.push({
					tool: 'retracement',
					pointIndex: 0,
					x: x1,
					y: y1,
					originalPoint: retracement.p1
				});
				allProjectedPointsForMouse.push({
					tool: 'retracement',
					pointIndex: 1,
					x: x2,
					y: y2,
					originalPoint: retracement.p2
				});

				const computedLevels = calculateRetracementLevels(
					retracement.p1,
					retracement.p2,
					retracement.levels
				);

				const projectedLevels = projectLevels(computedLevels, series);

				retracementRenderData = {
					p1: p1Projected,
					p2: p2Projected,
					levels: projectedLevels,
					extendLines: retracement.extendLines,
					visible: retracement.visible,
					isSelected: isRetracementSelected
				};
			}
		}

		// 2. Extension calculation
		let extensionRenderData: ExtensionRenderData | null = null;
		const extension = this._state.getExtension();

		if (extension && extension.visible !== false) {
			const x1 = this._timeProjector.timeToCoordinate(extension.p1.time);
			const y1 = series.priceToCoordinate(extension.p1.price);
			const x2 = this._timeProjector.timeToCoordinate(extension.p2.time);
			const y2 = series.priceToCoordinate(extension.p2.price);
			const x3 = this._timeProjector.timeToCoordinate(extension.p3.time);
			const y3 = series.priceToCoordinate(extension.p3.price);

			if (x1 !== null && y1 !== null && x2 !== null && y2 !== null && x3 !== null && y3 !== null) {
				const isP1Hovered = hovered?.tool === 'extension' && hovered?.pointIndex === 0;
				const isP1Dragging = dragging?.tool === 'extension' && dragging?.pointIndex === 0;
				const isP2Hovered = hovered?.tool === 'extension' && hovered?.pointIndex === 1;
				const isP2Dragging = dragging?.tool === 'extension' && dragging?.pointIndex === 1;
				const isP3Hovered = hovered?.tool === 'extension' && hovered?.pointIndex === 2;
				const isP3Dragging = dragging?.tool === 'extension' && dragging?.pointIndex === 2;

				const p1Projected: ProjectedFibPoint = {
					pointIndex: 0,
					x: x1,
					y: y1,
					time: extension.p1.time,
					price: extension.p1.price,
					isHovered: isP1Hovered,
					isDragging: isP1Dragging,
					isSelected: isExtensionSelected
				};

				const p2Projected: ProjectedFibPoint = {
					pointIndex: 1,
					x: x2,
					y: y2,
					time: extension.p2.time,
					price: extension.p2.price,
					isHovered: isP2Hovered,
					isDragging: isP2Dragging,
					isSelected: isExtensionSelected
				};

				const p3Projected: ProjectedFibPoint = {
					pointIndex: 2,
					x: x3,
					y: y3,
					time: extension.p3.time,
					price: extension.p3.price,
					isHovered: isP3Hovered,
					isDragging: isP3Dragging,
					isSelected: isExtensionSelected
				};

				allProjectedPointsForMouse.push({
					tool: 'extension',
					pointIndex: 0,
					x: x1,
					y: y1,
					originalPoint: extension.p1
				});
				allProjectedPointsForMouse.push({
					tool: 'extension',
					pointIndex: 1,
					x: x2,
					y: y2,
					originalPoint: extension.p2
				});
				allProjectedPointsForMouse.push({
					tool: 'extension',
					pointIndex: 2,
					x: x3,
					y: y3,
					originalPoint: extension.p3
				});

				const computedLevels = calculateExtensionLevels(
					extension.p1,
					extension.p2,
					extension.p3,
					extension.levels
				);

				const projectedLevels = projectLevels(computedLevels, series);

				extensionRenderData = {
					p1: p1Projected,
					p2: p2Projected,
					p3: p3Projected,
					levels: projectedLevels,
					extendLines: extension.extendLines,
					visible: extension.visible,
					isSelected: isExtensionSelected
				};
			}
		}

		this._mouseHandlers.setProjectedPoints(allProjectedPointsForMouse);

		// 3. Live Drawing Preview
		let preview: FibDrawingPreviewData | null = null;
		if (this._state.isDrawingMode()) {
			const activeTool = this._state.getActiveTool() ?? 'retracement';
			const pending = this._state.getPendingPoints();

			const placedPoints: ProjectedFibPoint[] = [];
			for (let i = 0; i < pending.length; i++) {
				const pt = pending[i];
				const x = this._timeProjector.timeToCoordinate(pt.time);
				const y = series.priceToCoordinate(pt.price);
				if (x !== null && y !== null) {
					placedPoints.push({
						pointIndex: i as 0 | 1 | 2,
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

			let previewLevels: ProjectedFibLevel[] | undefined = undefined;

			if (currentMouse && currentMouse.price !== null && currentMouse.price !== undefined) {
				if (activeTool === 'retracement' && pending.length === 1) {
					const previewComputed = calculateRetracementLevels(
						pending[0],
						{
							time: (currentMouse.time ?? pending[0].time) as Time,
							price: currentMouse.price
						},
						null
					);
					previewLevels = projectLevels(previewComputed, series);
				} else if (activeTool === 'extension' && pending.length === 2) {
					const previewComputed = calculateExtensionLevels(
						pending[0],
						pending[1],
						{
							time: (currentMouse.time ?? pending[1].time) as Time,
							price: currentMouse.price
						},
						null
					);
					previewLevels = projectLevels(previewComputed, series);
				}
			}

			preview = {
				tool: activeTool,
				placedPoints,
				currentMouse,
				previewLevels
			};
		}

		return {
			retracement: retracementRenderData,
			extension: extensionRenderData,
			preview
		};
	}
}
