import type {
	IChartApi,
	ISeriesApi,
	ISeriesPrimitive,
	IPrimitivePaneView,
	PrimitiveHoveredItem,
	SeriesAttachedParameter,
	SeriesType,
	Time
} from 'lightweight-charts';
import type { ISubscription } from '../helpers/delegate';
import {
	calculateExtensionLevels,
	calculateRetracementLevels,
	type FibExtensionDrawing,
	type FibPoint,
	type FibRetracementDrawing,
	type FibToolType,
	type SecurityFibonacciTools
} from '$lib/utils/finance/fibonacci';
import type { Candle } from '$lib/utils/finance/candle';
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
import { TimeProjector } from '../elliott-wave/time-projector';

export class FibonacciPrimitive implements ISeriesPrimitive<Time> {
	private _chart: IChartApi | undefined = undefined;
	private _series: ISeriesApi<SeriesType> | undefined = undefined;
	private _requestUpdate: (() => void) | undefined = undefined;

	private readonly _state: FibonacciToolState;
	private readonly _mouseHandlers: MouseHandlers;
	private readonly _timeProjector: TimeProjector;
	private readonly _paneViews: [FibonacciPaneView];

	private _currentCursor: string | null = null;

	constructor(initialState?: {
		activeTool?: FibToolType | null;
		drawings?: SecurityFibonacciTools;
		isDrawingMode?: boolean;
	}) {
		this._state = new FibonacciToolState();
		this._mouseHandlers = new MouseHandlers();
		this._timeProjector = new TimeProjector();
		this._paneViews = [new FibonacciPaneView()];

		if (initialState?.activeTool !== undefined) {
			this._state.setActiveTool(initialState.activeTool);
		}
		if (initialState?.drawings) {
			this._state.setDrawings(initialState.drawings);
		}
		if (initialState?.isDrawingMode !== undefined) {
			this._state.setDrawingMode(initialState.isDrawingMode);
		}
	}

	public attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>): void {
		this._chart = chart;
		this._series = series;
		this._requestUpdate = requestUpdate;

		this._timeProjector.attach(chart);
		this._mouseHandlers.attached(chart, series, this._timeProjector);
		this._mouseHandlers.setDrawingMode(this._state.isDrawingMode());

		this._state.drawingsChanged().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._state.drawingModeChanged().subscribe((isDrawing) => {
			this._mouseHandlers.setDrawingMode(isDrawing);
			this._requestUpdate?.();
		}, this);

		this._state.toolChanged().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._state.hoverChanged().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._state.dragChanged().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.mouseMoved().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.pointHovered().subscribe((target) => {
			this._state.setHoveredPoint(target);
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.dragStarted().subscribe((target) => {
			this._state.setDraggingPoint(target);
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.pointDragged().subscribe((dragEvent) => {
			this._state.updatePoint(dragEvent.tool, dragEvent.pointIndex, {
				time: dragEvent.time,
				price: dragEvent.price
			});
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.dragEnded().subscribe(() => {
			this._state.setDraggingPoint(null);
			this._requestUpdate?.();
		}, this);

		this._mouseHandlers.chartClicked().subscribe((clickEvent) => {
			if (this._state.isDrawingMode()) {
				this._state.addPoint({
					time: clickEvent.time,
					price: clickEvent.price
				});
				this._requestUpdate?.();
			}
		}, this);

		this._requestUpdate?.();
	}

	public detached(): void {
		this._state.drawingsChanged().unsubscribeAll(this);
		this._state.drawingModeChanged().unsubscribeAll(this);
		this._state.toolChanged().unsubscribeAll(this);
		this._state.hoverChanged().unsubscribeAll(this);
		this._state.dragChanged().unsubscribeAll(this);

		this._mouseHandlers.mouseMoved().unsubscribeAll(this);
		this._mouseHandlers.pointHovered().unsubscribeAll(this);
		this._mouseHandlers.dragStarted().unsubscribeAll(this);
		this._mouseHandlers.pointDragged().unsubscribeAll(this);
		this._mouseHandlers.dragEnded().unsubscribeAll(this);
		this._mouseHandlers.chartClicked().unsubscribeAll(this);

		this._mouseHandlers.detached();
		this._chart = undefined;
		this._series = undefined;
		this._requestUpdate = undefined;
	}

	public paneViews(): readonly IPrimitivePaneView[] {
		return this._paneViews;
	}

	public updateAllViews(): void {
		if (!this._chart || !this._series) {
			this._paneViews[0].update(null);
			return;
		}

		const rendererData = this._calculateRendererData();
		this._updateCursor();
		this._paneViews[0].update(rendererData);
	}

	public hitTest(): PrimitiveHoveredItem | null {
		if (!this._currentCursor) return null;
		return {
			cursorStyle: this._currentCursor,
			externalId: 'fibonacci-primitive',
			zOrder: 'top'
		};
	}

	// State and Public API Accessors
	public isDrawingMode(): boolean {
		return this._state.isDrawingMode();
	}

	public setDrawingMode(enabled: boolean): void {
		this._state.setDrawingMode(enabled);
	}

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

	public getHoveredPoint(): FibPointTarget | null {
		return this._state.getHoveredPoint();
	}

	public getDraggingPoint(): FibPointTarget | null {
		return this._state.getDraggingPoint();
	}

	public setCandles(candles: Candle[]): void {
		this._timeProjector.updateCandles(candles);
		this._requestUpdate?.();
	}

	public drawingsChanged(): ISubscription<SecurityFibonacciTools> {
		return this._state.drawingsChanged();
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._state.drawingModeChanged();
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

	public destroy(): void {
		this.detached();
		this._state.destroy();
	}

	private _updateCursor(): void {
		if (this._state.getDraggingPoint()) {
			this._currentCursor = 'grabbing';
		} else if (this._state.isDrawingMode()) {
			this._currentCursor = 'crosshair';
		} else if (this._state.getHoveredPoint()) {
			this._currentCursor = 'grab';
		} else {
			this._currentCursor = null;
		}
	}

	private _calculateRendererData(): FibonacciRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const allProjectedPointsForMouse: ProjectedFibPointWithTarget[] = [];
		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();

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
					isDragging: isP1Dragging
				};

				const p2Projected: ProjectedFibPoint = {
					pointIndex: 1,
					x: x2,
					y: y2,
					time: retracement.p2.time,
					price: retracement.p2.price,
					isHovered: isP2Hovered,
					isDragging: isP2Dragging
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

				retracementRenderData = {
					p1: p1Projected,
					p2: p2Projected,
					levels: projectedLevels,
					extendLines: retracement.extendLines,
					visible: retracement.visible
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
					isDragging: isP1Dragging
				};

				const p2Projected: ProjectedFibPoint = {
					pointIndex: 1,
					x: x2,
					y: y2,
					time: extension.p2.time,
					price: extension.p2.price,
					isHovered: isP2Hovered,
					isDragging: isP2Dragging
				};

				const p3Projected: ProjectedFibPoint = {
					pointIndex: 2,
					x: x3,
					y: y3,
					time: extension.p3.time,
					price: extension.p3.price,
					isHovered: isP3Hovered,
					isDragging: isP3Dragging
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

				extensionRenderData = {
					p1: p1Projected,
					p2: p2Projected,
					p3: p3Projected,
					levels: projectedLevels,
					extendLines: extension.extendLines,
					visible: extension.visible
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
					const lvls: ProjectedFibLevel[] = [];
					for (const lvl of previewComputed) {
						const y = series.priceToCoordinate(lvl.price);
						if (y !== null) {
							lvls.push({
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
					previewLevels = lvls;
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
					const lvls: ProjectedFibLevel[] = [];
					for (const lvl of previewComputed) {
						const y = series.priceToCoordinate(lvl.price);
						if (y !== null) {
							lvls.push({
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
					previewLevels = lvls;
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
