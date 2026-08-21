import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import type { WaveDegree, WavePoint } from '$lib/utils/finance/elliott-wave';
import { HIT_TEST_RADIUS } from './constants';
import type { PointTarget } from './state';
import type { TimeProjector } from './time-projector';

export interface MousePosition {
	x: number;
	y: number;
	time: Time | null;
	price: number | null;
	insidePlotArea: boolean;
}

export interface ProjectedPointWithTarget {
	degree: WaveDegree;
	wave: 0 | 1 | 2 | 3 | 4 | 5;
	x: number;
	y: number;
	originalPoint: WavePoint;
}

type Unsubscriber = () => void;

export class MouseHandlers {
	private _chart: IChartApi | undefined = undefined;
	private _series: ISeriesApi<SeriesType> | undefined = undefined;
	private _timeProjector: TimeProjector | undefined = undefined;
	private _unsubscribers: Unsubscriber[] = [];

	private _projectedPoints: ProjectedPointWithTarget[] = [];
	private _isDrawingMode: boolean = false;
	private _isDragging: boolean = false;
	private _dragTarget: PointTarget | null = null;
	private _lastMousePosition: MousePosition | null = null;
	private _savedPressedMouseMove: boolean | undefined = undefined;

	private _mouseMoved: Delegate<MousePosition | null> = new Delegate();
	private _chartClicked: Delegate<{ time: Time; price: number; x: number; y: number }> =
		new Delegate();
	private _pointClicked: Delegate<{
		degree: WaveDegree;
		wave: 0 | 1 | 2 | 3 | 4 | 5;
		point: WavePoint;
	}> = new Delegate();
	private _pointHovered: Delegate<PointTarget | null> = new Delegate();
	private _dragStarted: Delegate<PointTarget> = new Delegate();
	private _pointDragged: Delegate<{
		degree: WaveDegree;
		wave: 0 | 1 | 2 | 3 | 4 | 5;
		time: Time;
		price: number;
		x: number;
		y: number;
	}> = new Delegate();
	private _dragEnded: Delegate<PointTarget> = new Delegate();

	public attached(
		chart: IChartApi,
		series: ISeriesApi<SeriesType>,
		timeProjector?: TimeProjector
	): void {
		this._chart = chart;
		this._series = series;
		this._timeProjector = timeProjector;
		const container = chart.chartElement();

		this._addDOMListener(container, 'mousemove', this._onMouseMove.bind(this));
		this._addDOMListener(container, 'mousedown', this._onMouseDown.bind(this));
		this._addDOMListener(container, 'mouseup', this._onMouseUp.bind(this));
		this._addDOMListener(container, 'click', this._onClick.bind(this));
		this._addDOMListener(container, 'mouseleave', this._onMouseLeave.bind(this));

		if (typeof window !== 'undefined') {
			const onWindowMouseUp = () => this._onMouseUp();
			window.addEventListener('mouseup', onWindowMouseUp);
			this._unsubscribers.push(() => {
				window.removeEventListener('mouseup', onWindowMouseUp);
			});
		}
	}

	public detached(): void {
		this._restoreChartScroll();
		this._chart = undefined;
		this._series = undefined;
		this._projectedPoints = [];
		this._isDragging = false;
		this._dragTarget = null;
		this._lastMousePosition = null;

		this._mouseMoved.destroy();
		this._chartClicked.destroy();
		this._pointClicked.destroy();
		this._pointHovered.destroy();
		this._dragStarted.destroy();
		this._pointDragged.destroy();
		this._dragEnded.destroy();

		for (const unsub of this._unsubscribers) {
			unsub();
		}
		this._unsubscribers = [];
	}

	public setProjectedPoints(points: ProjectedPointWithTarget[]): void {
		this._projectedPoints = points;
	}

	public setDrawingMode(isDrawing: boolean): void {
		this._isDrawingMode = isDrawing;
		if (isDrawing && this._isDragging) {
			this._isDragging = false;
			this._dragTarget = null;
			this._restoreChartScroll();
		}
	}

	/**
	 * Prevents the underlying chart from panning while a wave point is being
	 * dragged (pressed mouse move scroll). Chart scrolling is restored on drag
	 * end so normal pan/scroll behaviour is unaffected otherwise.
	 */
	private _disableChartScroll(): void {
		if (!this._chart) return;
		if (this._savedPressedMouseMove === undefined) {
			const handleScroll = this._chart.options()?.handleScroll;
			this._savedPressedMouseMove =
				typeof handleScroll === 'object' && handleScroll !== null
					? handleScroll.pressedMouseMove
					: handleScroll !== false; // boolean shorthand; default (true) enables pressed-move scroll
		}
		this._chart.applyOptions({ handleScroll: { pressedMouseMove: false } });
	}

	private _restoreChartScroll(): void {
		if (!this._chart) return;
		if (this._savedPressedMouseMove !== undefined) {
			this._chart.applyOptions({
				handleScroll: { pressedMouseMove: this._savedPressedMouseMove }
			});
		}
		this._savedPressedMouseMove = undefined;
	}

	public getLastMousePosition(): MousePosition | null {
		return this._lastMousePosition;
	}

	public isDragging(): boolean {
		return this._isDragging;
	}

	public getDragTarget(): PointTarget | null {
		return this._dragTarget;
	}

	public mouseMoved(): ISubscription<MousePosition | null> {
		return this._mouseMoved;
	}

	public chartClicked(): ISubscription<{ time: Time; price: number; x: number; y: number }> {
		return this._chartClicked;
	}

	public pointClicked(): ISubscription<{
		degree: WaveDegree;
		wave: 0 | 1 | 2 | 3 | 4 | 5;
		point: WavePoint;
	}> {
		return this._pointClicked;
	}

	public pointHovered(): ISubscription<PointTarget | null> {
		return this._pointHovered;
	}

	public dragStarted(): ISubscription<PointTarget> {
		return this._dragStarted;
	}

	public pointDragged(): ISubscription<{
		degree: WaveDegree;
		wave: 0 | 1 | 2 | 3 | 4 | 5;
		time: Time;
		price: number;
		x: number;
		y: number;
	}> {
		return this._pointDragged;
	}

	public dragEnded(): ISubscription<PointTarget> {
		return this._dragEnded;
	}

	private _addDOMListener(
		target: HTMLElement,
		eventType: string,
		handler: (e: MouseEvent) => void
	): void {
		target.addEventListener(eventType, handler as EventListener);
		this._unsubscribers.push(() => {
			target.removeEventListener(eventType, handler as EventListener);
		});
	}

	private _determineMousePosition(event: MouseEvent): MousePosition | null {
		if (!this._chart || !this._series) return null;
		const element = this._chart.chartElement();
		const rect = element.getBoundingClientRect();
		const priceScaleWidth = this._series.priceScale().width();
		const timeScaleHeight = this._chart.timeScale().height();

		const x = event.clientX - rect.left;
		const y = event.clientY - rect.top;

		const insidePlotArea =
			x >= 0 &&
			x <= element.clientWidth - priceScaleWidth &&
			y >= 0 &&
			y <= element.clientHeight - timeScaleHeight;

		const time = insidePlotArea
			? this._timeProjector
				? this._timeProjector.coordinateToTime(x)
				: this._chart.timeScale().coordinateToTime(x)
			: null;
		const price = insidePlotArea ? this._series.coordinateToPrice(y) : null;

		return {
			x,
			y,
			time,
			price,
			insidePlotArea
		};
	}

	public hitTestPoint(x: number, y: number): ProjectedPointWithTarget | null {
		let closestPoint: ProjectedPointWithTarget | null = null;
		let closestDist = HIT_TEST_RADIUS;

		for (const pt of this._projectedPoints) {
			const dist = Math.hypot(x - pt.x, y - pt.y);
			if (dist <= closestDist) {
				closestDist = dist;
				closestPoint = pt;
			}
		}

		return closestPoint;
	}

	private _onMouseMove(event: MouseEvent): void {
		const pos = this._determineMousePosition(event);
		this._lastMousePosition = pos;

		if (!pos) {
			this._mouseMoved.fire(null);
			return;
		}

		if (this._isDragging && this._dragTarget) {
			if (pos.time !== null && pos.price !== null) {
				this._pointDragged.fire({
					degree: this._dragTarget.degree,
					wave: this._dragTarget.wave,
					time: pos.time,
					price: pos.price,
					x: pos.x,
					y: pos.y
				});
			}
		} else if (!this._isDrawingMode) {
			const hit = this.hitTestPoint(pos.x, pos.y);
			this._pointHovered.fire(hit ? { degree: hit.degree, wave: hit.wave } : null);
		} else {
			this._pointHovered.fire(null);
		}

		this._mouseMoved.fire(pos);
	}

	private _onMouseDown(event: MouseEvent): void {
		if (this._isDrawingMode) return;
		const pos = this._determineMousePosition(event);
		if (!pos) return;

		const hit = this.hitTestPoint(pos.x, pos.y);
		if (hit) {
			this._isDragging = true;
			this._dragTarget = { degree: hit.degree, wave: hit.wave };
			this._disableChartScroll();
			this._dragStarted.fire(this._dragTarget);
		}
	}

	private _onMouseUp(): void {
		if (this._isDragging && this._dragTarget) {
			const target = this._dragTarget;
			this._isDragging = false;
			this._dragTarget = null;
			this._restoreChartScroll();
			this._dragEnded.fire(target);
		}
	}

	private _onClick(event: MouseEvent): void {
		const pos = this._determineMousePosition(event);
		if (!pos) return;

		if (this._isDrawingMode) {
			if (pos.insidePlotArea && pos.time !== null && pos.price !== null) {
				this._chartClicked.fire({
					time: pos.time,
					price: pos.price,
					x: pos.x,
					y: pos.y
				});
			}
		} else {
			const hit = this.hitTestPoint(pos.x, pos.y);
			if (hit) {
				this._pointClicked.fire({
					degree: hit.degree,
					wave: hit.wave,
					point: hit.originalPoint
				});
			}
		}
	}

	private _onMouseLeave(): void {
		this._lastMousePosition = null;
		if (!this._isDragging) {
			this._pointHovered.fire(null);
			this._mouseMoved.fire(null);
		}
	}
}
