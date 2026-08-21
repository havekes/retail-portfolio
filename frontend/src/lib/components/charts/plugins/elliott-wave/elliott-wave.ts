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
import type { DegreeWaveCount, WaveDegree, WavePoint } from '$lib/utils/finance/elliott-wave';
import type { Candle } from '$lib/utils/finance/candle';
import { DEGREE_STYLES, MAX_WAVE_POINTS } from './constants';
import { MouseHandlers, type ProjectedPointWithTarget } from './mouse';
import {
	type DegreeRenderData,
	type DrawingPreviewData,
	type ElliottWaveRendererData,
	type ProjectedWavePoint
} from './pane-renderer';
import { ElliottWavePaneView } from './pane-view';
import { ElliottWaveState } from './state';
import { TimeProjector } from './time-projector';

export class ElliottWavesPrimitive implements ISeriesPrimitive<Time> {
	private _chart: IChartApi | undefined = undefined;
	private _series: ISeriesApi<SeriesType> | undefined = undefined;
	private _requestUpdate: (() => void) | undefined = undefined;

	private readonly _state: ElliottWaveState;
	private readonly _mouseHandlers: MouseHandlers;
	private readonly _timeProjector: TimeProjector;
	private readonly _paneViews: [ElliottWavePaneView];

	private _currentCursor: string | null = null;

	constructor(initialState?: {
		activeDegree?: WaveDegree;
		waves?: Record<WaveDegree, DegreeWaveCount | null>;
	}) {
		this._state = new ElliottWaveState();
		this._mouseHandlers = new MouseHandlers();
		this._timeProjector = new TimeProjector();
		this._paneViews = [new ElliottWavePaneView()];

		if (initialState?.activeDegree) {
			this._state.setActiveDegree(initialState.activeDegree);
		}
		if (initialState?.waves) {
			this._state.setAllWaveCounts(initialState.waves);
		}
	}

	public attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>): void {
		this._chart = chart;
		this._series = series;
		this._requestUpdate = requestUpdate;

		this._timeProjector.attach(chart);
		this._mouseHandlers.attached(chart, series, this._timeProjector);
		this._mouseHandlers.setDrawingMode(this._state.isDrawingMode());

		this._state.wavePointsChanged().subscribe(() => {
			this._requestUpdate?.();
		}, this);

		this._state.drawingModeChanged().subscribe((isDrawing) => {
			this._mouseHandlers.setDrawingMode(isDrawing);
			this._requestUpdate?.();
		}, this);

		this._state.degreeChanged().subscribe(() => {
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
			this._state.updatePoint(
				dragEvent.wave,
				{ time: dragEvent.time, price: dragEvent.price },
				dragEvent.degree
			);
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

		this._requestUpdate();
	}

	public detached(): void {
		this._state.wavePointsChanged().unsubscribeAll(this);
		this._state.drawingModeChanged().unsubscribeAll(this);
		this._state.degreeChanged().unsubscribeAll(this);

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
			externalId: 'elliott-waves-primitive',
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

	public getActiveDegree(): WaveDegree {
		return this._state.getActiveDegree();
	}

	public setActiveDegree(degree: WaveDegree): void {
		this._state.setActiveDegree(degree);
	}

	public getWaveCount(degree?: WaveDegree): DegreeWaveCount | null {
		return this._state.getWaveCount(degree);
	}

	public setWaveCount(degree: WaveDegree, waveCount: DegreeWaveCount | null): void {
		this._state.setWaveCount(degree, waveCount);
	}

	public getAllWaveCounts(): Record<WaveDegree, DegreeWaveCount | null> {
		return this._state.getAllWaveCounts();
	}

	public setAllWaveCounts(waves: Record<WaveDegree, DegreeWaveCount | null>): void {
		this._state.setAllWaveCounts(waves);
	}

	/**
	 * Provide the latest candle data so future (beyond last data point) wave
	 * times can be extrapolated for placement, dragging, and rendering.
	 */
	public setCandles(candles: Candle[]): void {
		this._timeProjector.updateCandles(candles);
		this._requestUpdate?.();
	}

	public getPoints(degree?: WaveDegree): WavePoint[] {
		return this._state.getPoints(degree);
	}

	public addPoint(
		pointOrPrice: { time: Time; price: number } | number,
		timeOrDegree?: Time | WaveDegree,
		maybeDegree?: WaveDegree
	): WavePoint {
		if (typeof pointOrPrice === 'number') {
			const price = pointOrPrice;
			const time = timeOrDegree as Time;
			const degree = maybeDegree;
			return this._state.addPoint({ time, price }, degree);
		} else {
			const point = pointOrPrice;
			const degree = timeOrDegree as WaveDegree | undefined;
			return this._state.addPoint(point, degree);
		}
	}

	public updatePoint(
		wave: 0 | 1 | 2 | 3 | 4 | 5,
		updateOrPrice: { time?: Time; price?: number } | number,
		timeOrDegree?: Time | WaveDegree,
		maybeDegree?: WaveDegree
	): boolean {
		if (typeof updateOrPrice === 'number') {
			const price = updateOrPrice;
			const time = timeOrDegree as Time | undefined;
			const degree = maybeDegree;
			return this._state.updatePoint(wave, { price, time }, degree);
		} else {
			const update = updateOrPrice;
			const degree = timeOrDegree as WaveDegree | undefined;
			return this._state.updatePoint(wave, update, degree);
		}
	}

	public clearWave(degree?: WaveDegree): void {
		this._state.clearWave(degree);
	}

	public wavePointsChanged(): ISubscription<{
		degree: WaveDegree;
		waveCount: DegreeWaveCount | null;
	}> {
		return this._state.wavePointsChanged();
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._state.drawingModeChanged();
	}

	public degreeChanged(): ISubscription<WaveDegree> {
		return this._state.degreeChanged();
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

	private _calculateRendererData(): ElliottWaveRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const degrees: WaveDegree[] = ['cycle', 'primary'];

		const allProjectedPointsForMouse: ProjectedPointWithTarget[] = [];
		const degreeRenderDataList: DegreeRenderData[] = [];

		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const activeDegree = this._state.getActiveDegree();

		for (const degree of degrees) {
			const config = DEGREE_STYLES[degree];
			const waveCount = this._state.getWaveCount(degree);
			const points = waveCount?.points ?? [];
			const projectedPoints: ProjectedWavePoint[] = [];

			for (const pt of points) {
				const x = this._timeProjector.timeToCoordinate(pt.time);
				const y = series.priceToCoordinate(pt.price);

				if (x !== null && y !== null) {
					const isHovered = hovered?.degree === degree && hovered?.wave === pt.wave;
					const isDragging = dragging?.degree === degree && dragging?.wave === pt.wave;

					const projectedPoint: ProjectedWavePoint = {
						wave: pt.wave,
						x,
						y,
						time: pt.time,
						price: pt.price,
						isHovered,
						isDragging
					};

					projectedPoints.push(projectedPoint);
					allProjectedPointsForMouse.push({
						degree,
						wave: pt.wave,
						x,
						y,
						originalPoint: pt
					});
				}
			}

			degreeRenderDataList.push({
				degree,
				config,
				points: projectedPoints,
				isActiveDegree: degree === activeDegree
			});
		}

		this._mouseHandlers.setProjectedPoints(allProjectedPointsForMouse);

		let preview: DrawingPreviewData | null = null;
		if (this._state.isDrawingMode()) {
			const activeConfig = DEGREE_STYLES[activeDegree];
			const activeDegreeData = degreeRenderDataList.find((d) => d.degree === activeDegree);
			const activePoints = activeDegreeData?.points ?? [];

			if (activePoints.length < MAX_WAVE_POINTS) {
				const nextWave = activePoints.length as 0 | 1 | 2 | 3 | 4 | 5;
				const lastPoint = activePoints.length > 0 ? activePoints[activePoints.length - 1] : null;
				const lastMouse = this._mouseHandlers.getLastMousePosition();

				preview = {
					degree: activeDegree,
					config: activeConfig,
					nextWave,
					lastPoint,
					currentMouse:
						lastMouse && lastMouse.insidePlotArea ? { x: lastMouse.x, y: lastMouse.y } : null
				};
			}
		}

		return {
			degrees: degreeRenderDataList,
			preview
		};
	}
}
