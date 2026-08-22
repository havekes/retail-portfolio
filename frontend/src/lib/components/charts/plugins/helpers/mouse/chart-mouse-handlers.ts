import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../delegate';
import type { TimeProjector } from '../time/time-projector';
import type { MousePosition } from './mouse-position';

type Unsubscriber = () => void;

export interface ChartMouseHandlersConfig<TPoint, TTarget> {
	/** Maximum distance in pixels from a projected point for a hit to register. */
	hitTestRadius: number;
	/**
	 * Maps a projected point to the plugin-specific target key embedded in the
	 * delegate payloads (e.g. `{ tool, pointIndex }` vs `{ degree, wave }`).
	 */
	toTarget: (point: TPoint) => TTarget;
	/**
	 * Optional position adjustment applied immediately before firing `chartClicked`
	 * (drawing mode) and `pointDragged` (drag moves). Used by the Elliott plugin
	 * to snap to candle wicks. Only invoked when the resolved position carries a
	 * non-null price.
	 */
	adjustPosition?: (
		pos: MousePosition,
		series: ISeriesApi<SeriesType>
	) => { price: number; y: number };
}

/**
 * Generic mouse interaction handler for chart drawing plugins. Covers DOM
 * listener attach/detach (including window mouseup), plot-area mouse-position
 * resolution, hit testing with a configurable radius, the drag lifecycle with
 * click suppression, chart-scroll lock/restore during drags, drawing-mode
 * state, and the eight-delegate event surface shared by the fibonacci and
 * elliott-wave plugins.
 */
export class ChartMouseHandlers<
	TPoint extends { x: number; y: number; originalPoint: TOriginal },
	TTarget,
	TOriginal
> {
	private readonly _config: ChartMouseHandlersConfig<TPoint, TTarget>;

	private _chart: IChartApi | undefined = undefined;
	private _series: ISeriesApi<SeriesType> | undefined = undefined;
	private _timeProjector: TimeProjector | undefined = undefined;
	private _unsubscribers: Unsubscriber[] = [];

	private _projectedPoints: TPoint[] = [];
	private _isDrawingMode: boolean = false;
	private _isDragging: boolean = false;
	private _dragHappened: boolean = false;
	private _dragTarget: TTarget | null = null;
	private _lastMousePosition: MousePosition | null = null;
	private _savedPressedMouseMove: boolean | undefined = undefined;

	private _mouseMoved: Delegate<MousePosition | null> = new Delegate();
	private _chartClicked: Delegate<{ time: Time; price: number; x: number; y: number }> =
		new Delegate();
	private _pointClicked: Delegate<TTarget & { point: TOriginal }> = new Delegate();
	private _emptyAreaClicked: Delegate<void> = new Delegate();
	private _pointHovered: Delegate<TTarget | null> = new Delegate();
	private _dragStarted: Delegate<TTarget> = new Delegate();
	private _pointDragged: Delegate<TTarget & { time: Time; price: number; x: number; y: number }> =
		new Delegate();
	private _dragEnded: Delegate<TTarget> = new Delegate();

	constructor(config: ChartMouseHandlersConfig<TPoint, TTarget>) {
		this._config = config;
	}

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
		this._emptyAreaClicked.destroy();
		this._pointHovered.destroy();
		this._dragStarted.destroy();
		this._pointDragged.destroy();
		this._dragEnded.destroy();

		for (const unsub of this._unsubscribers) {
			unsub();
		}
		this._unsubscribers = [];
	}

	public setProjectedPoints(points: TPoint[]): void {
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
	 * Prevents the underlying chart from panning while a point is being dragged
	 * (pressed mouse move scroll). Chart scrolling is restored on drag end so
	 * normal pan/scroll behaviour is unaffected otherwise.
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

	public getDragTarget(): TTarget | null {
		return this._dragTarget;
	}

	public mouseMoved(): ISubscription<MousePosition | null> {
		return this._mouseMoved;
	}

	public chartClicked(): ISubscription<{ time: Time; price: number; x: number; y: number }> {
		return this._chartClicked;
	}

	public pointClicked(): ISubscription<TTarget & { point: TOriginal }> {
		return this._pointClicked;
	}

	public emptyAreaClicked(): ISubscription<void> {
		return this._emptyAreaClicked;
	}

	public pointHovered(): ISubscription<TTarget | null> {
		return this._pointHovered;
	}

	public dragStarted(): ISubscription<TTarget> {
		return this._dragStarted;
	}

	public pointDragged(): ISubscription<
		TTarget & { time: Time; price: number; x: number; y: number }
	> {
		return this._pointDragged;
	}

	public dragEnded(): ISubscription<TTarget> {
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

	/**
	 * Finds the projected point closest to (x, y) within `hitTestRadius`.
	 *
	 * Hit-test contract (unified across drawing plugins):
	 * - Boundary is inclusive: a point at exactly `hitTestRadius` distance is a hit.
	 * - Exact-distance ties resolve first-wins: the earliest point in the array at a
	 *   given distance wins, so plugins can rely on array order for overlapping anchors.
	 */
	public hitTestPoint(x: number, y: number): TPoint | null {
		let closestPoint: TPoint | null = null;
		let closestDist = Infinity;

		for (const pt of this._projectedPoints) {
			const dist = Math.hypot(x - pt.x, y - pt.y);
			if (dist <= this._config.hitTestRadius && dist < closestDist) {
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
			this._dragHappened = true;
			if (pos.time !== null && pos.price !== null) {
				let price = pos.price;
				let y = pos.y;
				if (this._config.adjustPosition && this._series) {
					const adjusted = this._config.adjustPosition(pos, this._series);
					price = adjusted.price;
					y = adjusted.y;
				}
				this._pointDragged.fire({
					...this._dragTarget,
					time: pos.time,
					price,
					x: pos.x,
					y
				});
			}
		} else if (!this._isDrawingMode) {
			const hit = this.hitTestPoint(pos.x, pos.y);
			this._pointHovered.fire(hit ? this._config.toTarget(hit) : null);
		} else {
			this._pointHovered.fire(null);
		}

		this._mouseMoved.fire(pos);
	}

	private _onMouseDown(event: MouseEvent): void {
		if (this._isDrawingMode) return;
		this._dragHappened = false;
		const pos = this._determineMousePosition(event);
		if (!pos) return;

		const hit = this.hitTestPoint(pos.x, pos.y);
		if (hit) {
			this._isDragging = true;
			this._dragTarget = this._config.toTarget(hit);
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
		if (this._dragHappened) {
			this._dragHappened = false;
			return;
		}

		const pos = this._determineMousePosition(event);
		if (!pos) return;

		if (this._isDrawingMode) {
			if (pos.insidePlotArea && pos.time !== null && pos.price !== null) {
				let price = pos.price;
				let y = pos.y;
				if (this._config.adjustPosition && this._series) {
					const adjusted = this._config.adjustPosition(pos, this._series);
					price = adjusted.price;
					y = adjusted.y;
				}
				this._chartClicked.fire({
					time: pos.time,
					price,
					x: pos.x,
					y
				});
			}
		} else {
			const hit = this.hitTestPoint(pos.x, pos.y);
			if (hit) {
				this._pointClicked.fire({
					...this._config.toTarget(hit),
					point: hit.originalPoint
				});
			} else if (pos.insidePlotArea) {
				this._emptyAreaClicked.fire();
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
