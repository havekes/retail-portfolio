import type { Time } from 'lightweight-charts';
import type { ISubscription } from '../helpers/delegate';
import type {
	DegreeWaveCount,
	WaveDegree,
	WavePoint,
	WavePointId,
	WaveType
} from '$lib/utils/finance/elliott-wave';
import type { Candle } from '$lib/utils/finance/candle';
import { DEGREE_STYLES, MAX_CORRECTIVE_POINTS, MAX_IMPULSE_POINTS } from './constants';
import { MouseHandlers, type ProjectedPointWithTarget, type ProjectedWaveSegment } from './mouse';
import {
	getWaveOrder,
	type DegreeRenderData,
	type DrawingPreviewData,
	type ElliottWaveRendererData,
	type ProjectedWavePoint
} from './pane-renderer';
import { ElliottWavePaneView } from './pane-view';
import { ElliottWaveState, type PointTarget, type WavePointsChangedEvent } from './state';
import { DrawingPrimitiveBase } from '../helpers/primitive/drawing-primitive-base';
import { timeToEpochSeconds } from '../helpers/time/time';

export class ElliottWavesPrimitive extends DrawingPrimitiveBase<
	ElliottWaveRendererData,
	ElliottWavePaneView,
	ElliottWaveState,
	MouseHandlers,
	PointTarget,
	PointTarget
> {
	private _snapToWicks: boolean = false;
	private _fibLevelPrices: number[] = [];

	constructor(initialState?: {
		activeDegree?: WaveDegree;
		activeWaveType?: WaveType;
		waves?: DegreeWaveCount[];
		snapToWicks?: boolean;
		selectedDegree?: WaveDegree | null;
		selectedWaveId?: string | null;
	}) {
		const state = new ElliottWaveState();
		const mouseHandlers = new MouseHandlers();
		const paneView = new ElliottWavePaneView();

		if (initialState?.activeDegree) {
			state.setActiveDegree(initialState.activeDegree);
		}
		if (initialState?.activeWaveType) {
			state.setActiveWaveType(initialState.activeWaveType);
		}
		if (initialState?.waves) {
			state.setWaves(initialState.waves);
		}
		if (initialState?.snapToWicks !== undefined) {
			mouseHandlers.setSnapToWicks(initialState.snapToWicks);
		}
		if (initialState?.selectedDegree !== undefined) {
			state.setSelectedDegree(initialState.selectedDegree);
		}
		if (initialState?.selectedWaveId !== undefined) {
			state.setSelectedWaveId(initialState.selectedWaveId);
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
		this._subscribeToUpdate(this._state.waveTypeChanged());
		this._subscribeToUpdate(this._state.selectionChanged());
		this._subscribeToUpdate(this._state.selectedWaveChanged());

		this._subscribe(this._mouseHandlers.pointClicked(), (hit) => {
			this._state.setSelectedWaveId(hit.waveId ?? null);
			this._state.setSelectedDegree(hit.degree);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.lineHovered(), (target) => {
			this._state.setHoveredPoint(target);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.lineClicked(), (hit) => {
			this._state.setSelectedWaveId(hit.waveId ?? null);
			this._state.setSelectedDegree(hit.degree);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.emptyAreaClicked(), () => {
			this._state.setSelectedWaveId(null);
			this._state.setSelectedDegree(null);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.pointDragged(), (dragEvent) => {
			this._state.updatePoint(
				dragEvent.wave,
				{ time: dragEvent.time, price: dragEvent.price },
				dragEvent.degree,
				dragEvent.waveId
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

	public getActiveWaveType(): WaveType {
		return this._state.getActiveWaveType();
	}

	public setActiveWaveType(type: WaveType): void {
		this._state.setActiveWaveType(type);
	}

	public waveTypeChanged(): ISubscription<WaveType> {
		return this._state.waveTypeChanged();
	}

	public getWaveCount(degree?: WaveDegree): DegreeWaveCount | null {
		return this._state.getWaveCount(degree);
	}

	public getWaves(degree?: WaveDegree): DegreeWaveCount[] {
		return this._state.getWaves(degree);
	}

	public getAllWaves(): DegreeWaveCount[] {
		return this._state.getAllWaves();
	}

	public getWaveById(id: string): DegreeWaveCount | undefined {
		return this._state.getWaveById(id);
	}

	public setWaves(waves: DegreeWaveCount[]): void {
		this._state.setWaves(waves);
	}

	public removeWave(id: string): boolean {
		return this._state.removeWave(id);
	}

	public getDrawingWave(): DegreeWaveCount | null {
		return this._state.getDrawingWave();
	}

	public getSelectedWaveId(): string | null {
		return this._state.getSelectedWaveId();
	}

	public setSelectedWaveId(waveId: string | null): void {
		this._state.setSelectedWaveId(waveId);
	}

	public selectedWaveChanged(): ISubscription<string | null> {
		return this._state.selectedWaveChanged();
	}

	/**
	 * Provide the latest candle data so future (beyond last data point) wave
	 * times can be extrapolated for placement, dragging, and rendering, and
	 * wave points can snap to candle wicks when snapToWicks is enabled.
	 */
	public override setCandles(candles: Candle[]): void {
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

	/**
	 * Provides the price of every currently enabled/drawn Fibonacci level, so wave-point
	 * placement, dragging, and the drawing-preview ghost can snap to them. Supplied by the
	 * chart owner from `$lib/utils/finance/fibonacci` (never imported from the sibling plugin).
	 */
	public setFibLevelPrices(prices: number[]): void {
		this._fibLevelPrices = Array.isArray(prices) ? [...prices] : [];
		this._mouseHandlers.setFibLevelPrices(this._fibLevelPrices);
		this._requestUpdate?.();
	}

	public getFibLevelPrices(): number[] {
		return [...this._fibLevelPrices];
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
		wave: WavePointId,
		updateOrPrice: { time?: Time; price?: number } | number,
		timeOrDegree?: Time | WaveDegree,
		maybeDegreeOrWaveId?: WaveDegree | string,
		maybeWaveId?: string
	): boolean {
		if (typeof updateOrPrice === 'number') {
			const price = updateOrPrice;
			const time = timeOrDegree as Time | undefined;
			const degree = maybeDegreeOrWaveId as WaveDegree | undefined;
			const waveId = maybeWaveId;
			return this._state.updatePoint(wave, { price, time }, degree, waveId);
		} else {
			const update = updateOrPrice;
			const degree = timeOrDegree as WaveDegree | undefined;
			const waveId = maybeDegreeOrWaveId as string | undefined;
			return this._state.updatePoint(wave, update, degree, waveId);
		}
	}

	public clearWave(waveIdOrDegree?: string | WaveDegree): void {
		this._state.clearWave(waveIdOrDegree);
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

	public wavePointsChanged(): ISubscription<WavePointsChangedEvent> {
		return this._state.wavePointsChanged();
	}

	public degreeChanged(): ISubscription<WaveDegree> {
		return this._state.degreeChanged();
	}

	protected override _calculateRendererData(): ElliottWaveRendererData | null {
		if (!this._chart || !this._series) return null;

		const series = this._series;
		const allProjectedPointsForMouse: ProjectedPointWithTarget[] = [];
		const allProjectedSegmentsForMouse: ProjectedWaveSegment[] = [];
		const degreeRenderDataList: DegreeRenderData[] = [];

		const hovered = this._state.getHoveredPoint();
		const dragging = this._state.getDraggingPoint();
		const activeDegree = this._state.getActiveDegree();
		const selectedDegree = this._state.getSelectedDegree();
		const selectedWaveId = this._state.getSelectedWaveId();

		const allWaves = this._state.getAllWaves();

		for (const wave of allWaves) {
			const waveDegree = wave.degree;
			const config = DEGREE_STYLES[waveDegree];
			const points = wave.points ?? [];
			const projectedPoints: ProjectedWavePoint[] = [];
			const isWaveSelected =
				(selectedWaveId !== null && wave.id === selectedWaveId) ||
				(selectedWaveId === null && selectedDegree !== null && waveDegree === selectedDegree);

			for (const pt of points) {
				const x = this._timeProjector.epochToCoordinate(timeToEpochSeconds(pt.time));
				const y = series.priceToCoordinate(pt.price);

				if (x !== null && y !== null) {
					// Hovering any point (or the connecting line) highlights every point
					// of that wave, so the whole wave reads as a single hovered unit.
					const isHovered = hovered?.waveId
						? hovered.waveId === wave.id
						: hovered?.degree === waveDegree && hovered?.wave === pt.wave;
					const isDragging = dragging?.waveId
						? dragging.waveId === wave.id && dragging.wave === pt.wave
						: dragging?.degree === waveDegree && dragging?.wave === pt.wave;

					const projectedPoint: ProjectedWavePoint = {
						wave: pt.wave,
						waveId: wave.id,
						x,
						y,
						time: pt.time,
						price: pt.price,
						isHovered,
						isDragging,
						isSelected: isWaveSelected
					};

					projectedPoints.push(projectedPoint);
					allProjectedPointsForMouse.push({
						degree: waveDegree,
						wave: pt.wave,
						waveId: wave.id,
						x,
						y,
						originalPoint: pt
					});
				}
			}

			const waveType = wave.type;

			const sortedPoints = [...projectedPoints].sort(
				(a, b) => getWaveOrder(a.wave) - getWaveOrder(b.wave)
			);
			for (let i = 1; i < sortedPoints.length; i++) {
				const prev = sortedPoints[i - 1];
				const curr = sortedPoints[i];
				if (getWaveOrder(curr.wave) === getWaveOrder(prev.wave) + 1) {
					allProjectedSegmentsForMouse.push({
						degree: waveDegree,
						wave: prev.wave,
						waveId: wave.id,
						x1: prev.x,
						y1: prev.y,
						x2: curr.x,
						y2: curr.y
					});
				}
			}

			degreeRenderDataList.push({
				id: wave.id,
				degree: waveDegree,
				type: waveType,
				config,
				points: projectedPoints,
				isActiveDegree: waveDegree === activeDegree,
				isSelected: isWaveSelected
			});
		}

		this._mouseHandlers.setProjectedPoints(allProjectedPointsForMouse);
		this._mouseHandlers.setProjectedSegments(allProjectedSegmentsForMouse);

		let preview: DrawingPreviewData | null = null;
		if (this._state.isDrawingMode()) {
			const activeWaveType = this._state.getActiveWaveType();
			const isCorrective = activeWaveType === 'corrective';
			const maxPoints = isCorrective ? MAX_CORRECTIVE_POINTS : MAX_IMPULSE_POINTS;
			const activeConfig = DEGREE_STYLES[activeDegree];

			const drawingWave = this._state.getDrawingWave();
			const drawingPoints = drawingWave?.points ?? [];

			if (drawingPoints.length < maxPoints) {
				const nextWave: WavePointId = isCorrective
					? (([0, 'A', 'B', 'C'] as const)[drawingPoints.length] ?? 0)
					: (drawingPoints.length as 0 | 1 | 2 | 3 | 4 | 5);

				let lastPoint: ProjectedWavePoint | null = null;
				if (drawingPoints.length > 0) {
					const lastPt = drawingPoints[drawingPoints.length - 1];
					const lx = this._timeProjector.epochToCoordinate(timeToEpochSeconds(lastPt.time));
					const ly = series.priceToCoordinate(lastPt.price);
					if (lx !== null && ly !== null) {
						lastPoint = {
							wave: lastPt.wave,
							waveId: drawingWave?.id,
							x: lx,
							y: ly,
							time: lastPt.time,
							price: lastPt.price
						};
					}
				}

				const lastMouse = this._mouseHandlers.getLastMousePosition();

				let currentMouse: { x: number; y: number } | null = null;
				if (lastMouse && lastMouse.insidePlotArea) {
					let y = lastMouse.y;
					if (lastMouse.time !== null && lastMouse.price !== null) {
						// Reuse the exact placement/drag resolution so the ghost lands where a
						// click would (wick- vs Fib-level snap).
						y = this._mouseHandlers.resolveAdjustedPosition(lastMouse, series).y;
					}
					currentMouse = { x: lastMouse.x, y };
				}

				preview = {
					degree: activeDegree,
					type: activeWaveType,
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
