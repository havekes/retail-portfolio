import type { Time } from 'lightweight-charts';
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
import { buildCandleLookup, findCandleByTime, snapPriceToWick } from './snap';
import { ElliottWaveState, type PointTarget } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';

export class ElliottWavesPrimitive extends DrawingPrimitiveBase<
	ElliottWaveRendererData,
	ElliottWavePaneView,
	ElliottWaveState,
	MouseHandlers,
	PointTarget,
	PointTarget
> {
	private _snapToWicks: boolean = false;
	private _candleLookup: Map<number, Candle> = new Map();

	constructor(initialState?: {
		activeDegree?: WaveDegree;
		waves?: Record<WaveDegree, DegreeWaveCount | null>;
		snapToWicks?: boolean;
		selectedDegree?: WaveDegree | null;
	}) {
		const state = new ElliottWaveState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new ElliottWavePaneView();

		if (initialState?.activeDegree) {
			state.setActiveDegree(initialState.activeDegree);
		}
		if (initialState?.waves) {
			state.setAllWaveCounts(initialState.waves);
		}
		if (initialState?.snapToWicks !== undefined) {
			mouseHandlers.setSnapToWicks(initialState.snapToWicks);
		}
		if (initialState?.selectedDegree !== undefined) {
			state.setSelectedDegree(initialState.selectedDegree);
		}

		super({
			externalId: 'elliott-waves-primitive',
			state,
			mouseHandlers,
			paneView
		});

		if (initialState?.snapToWicks !== undefined) {
			this._snapToWicks = initialState.snapToWicks;
		}
	}

	protected override _setupSubscriptions(): void {
		this._subscribeToUpdate(this._state.wavePointsChanged());
		this._subscribeToUpdate(this._state.degreeChanged());
		this._subscribeToUpdate(this._state.selectionChanged());

		this._subscribe(this._mouseHandlers.pointClicked(), (hit) => {
			this._state.setSelectedDegree(hit.degree);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.emptyAreaClicked(), () => {
			this._state.setSelectedDegree(null);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(
				dragEvent.wave,
				{ time: dragEvent.time, price: dragEvent.price },
				dragEvent.degree
			);
			this._requestUpdate?.();
		});
	}

	// State and Public API Accessors
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
	 * times can be extrapolated for placement, dragging, and rendering, and
	 * wave points can snap to candle wicks when snapToWicks is enabled.
	 */
	public override setCandles(candles: Candle[]): void {
		this._candleLookup = buildCandleLookup(candles);
		this._mouseHandlers.setCandles(candles);
		super.setCandles(candles);
	}

	public getSnapToWicks(): boolean {
		return this._snapToWicks;
	}

	public setSnapToWicks(enabled: boolean): void {
		this._snapToWicks = enabled;
		this._mouseHandlers.setSnapToWicks(enabled);
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

	public getSelectedDegree(): WaveDegree | null {
		return this._state.getSelectedDegree();
	}

	public setSelectedDegree(degree: WaveDegree | null): void {
		this._state.setSelectedDegree(degree);
	}

	public selectionChanged(): ISubscription<WaveDegree | null> {
		return this._state.selectionChanged();
	}

	public wavePointsChanged(): ISubscription<{
		degree: WaveDegree;
		waveCount: DegreeWaveCount | null;
	}> {
		return this._state.wavePointsChanged();
	}

	public degreeChanged(): ISubscription<WaveDegree> {
		return this._state.degreeChanged();
	}

	protected override _calculateRendererData(): ElliottWaveRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const degrees: WaveDegree[] = ['cycle', 'primary'];

		const allProjectedPointsForMouse: ProjectedPointWithTarget[] = [];
		const degreeRenderDataList: DegreeRenderData[] = [];

		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const activeDegree = this._state.getActiveDegree();
		const selectedDegree = this._state.getSelectedDegree();

		for (const degree of degrees) {
			const config = DEGREE_STYLES[degree];
			const waveCount = this._state.getWaveCount(degree);
			const points = waveCount?.points ?? [];
			const projectedPoints: ProjectedWavePoint[] = [];
			const isDegreeSelected = degree === selectedDegree;

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
						isDragging,
						isSelected: isDegreeSelected
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
				isActiveDegree: degree === activeDegree,
				isSelected: isDegreeSelected
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

				let currentMouse: { x: number; y: number } | null = null;
				if (lastMouse && lastMouse.insidePlotArea) {
					let y = lastMouse.y;
					if (this._snapToWicks && lastMouse.time !== null && lastMouse.price !== null) {
						const candle = findCandleByTime(this._candleLookup, lastMouse.time);
						if (candle) {
							const snappedPrice = snapPriceToWick(lastMouse.price, candle);
							const snappedY = series.priceToCoordinate(snappedPrice);
							if (snappedY !== null) {
								y = snappedY;
							}
						}
					}
					currentMouse = { x: lastMouse.x, y };
				}

				preview = {
					degree: activeDegree,
					config: activeConfig,
					nextWave,
					lastPoint,
					currentMouse
				};
			}
		}

		return {
			degrees: degreeRenderDataList,
			preview
		};
	}
}
