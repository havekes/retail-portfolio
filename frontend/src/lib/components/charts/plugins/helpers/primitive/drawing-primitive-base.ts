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
import type { ISubscription } from '../delegate';
import type { MousePosition } from '../mouse/mouse-position';
import { TimeProjector } from '../time/time-projector';
import type { Candle } from '$lib/utils/finance/candle';

export interface IDrawingToolState<THoverTarget = unknown, TDragTarget = unknown> {
	isDrawingMode(): boolean;
	setDrawingMode(enabled: boolean): void;
	drawingModeChanged(): ISubscription<boolean>;
	getHoveredPoint(): THoverTarget | null;
	setHoveredPoint(target: THoverTarget | null): void;
	getDraggingPoint(): TDragTarget | null;
	setDraggingPoint(target: TDragTarget | null): void;
	addPoint(point: { time: Time; price: number }): unknown;
	destroy(): void;
}

export interface IUpdatablePaneView<TRendererData> extends IPrimitivePaneView {
	update(data: TRendererData | null): void;
}

export interface IDrawingMouseHandlers<THoverTarget = unknown, TDragTarget = unknown> {
	attached(chart: IChartApi, series: ISeriesApi<SeriesType>, timeProjector?: TimeProjector): void;
	detached(): void;
	setDrawingMode(isDrawing: boolean): void;
	mouseMoved(): ISubscription<MousePosition | null>;
	pointHovered(): ISubscription<THoverTarget | null>;
	dragStarted(): ISubscription<TDragTarget>;
	dragEnded(): ISubscription<TDragTarget>;
	chartClicked(): ISubscription<{ time: Time; price: number; x: number; y: number }>;
}

export interface DrawingPrimitiveBaseConfig<
	TRendererData,
	TPaneView extends IUpdatablePaneView<TRendererData>,
	TState extends IDrawingToolState<THoverTarget, TDragTarget>,
	TMouseHandlers extends IDrawingMouseHandlers<THoverTarget, TDragTarget>,
	THoverTarget = unknown,
	TDragTarget = unknown
> {
	externalId: string;
	state: TState;
	mouseHandlers: TMouseHandlers;
	paneView: TPaneView;
	timeProjector?: TimeProjector;
}

/**
 * Abstract base class for drawing primitives (e.g. Fibonacci, Elliott Wave).
 *
 * Encapsulates chart/series attachment lifecycle, mouse handler integration,
 * delegate subscription tracking with automatic unsubscription on detach,
 * unified cursor resolution, and pane view updates.
 */
export abstract class DrawingPrimitiveBase<
	TRendererData,
	TPaneView extends IUpdatablePaneView<TRendererData>,
	TState extends IDrawingToolState<THoverTarget, TDragTarget>,
	TMouseHandlers extends IDrawingMouseHandlers<THoverTarget, TDragTarget>,
	THoverTarget = unknown,
	TDragTarget = unknown
> implements ISeriesPrimitive<Time> {
	protected _chart: IChartApi | undefined = undefined;
	protected _series: ISeriesApi<SeriesType> | undefined = undefined;
	protected _requestUpdate: (() => void) | undefined = undefined;

	protected readonly _externalId: string;
	protected readonly _state: TState;
	protected readonly _mouseHandlers: TMouseHandlers;
	protected readonly _timeProjector: TimeProjector;
	protected readonly _paneView: TPaneView;
	protected readonly _paneViews: [TPaneView];

	private _currentCursor: string | null = null;
	private _trackedSubscriptions: Set<ISubscription<unknown>> = new Set();

	constructor(
		config: DrawingPrimitiveBaseConfig<
			TRendererData,
			TPaneView,
			TState,
			TMouseHandlers,
			THoverTarget,
			TDragTarget
		>
	) {
		this._externalId = config.externalId;
		this._state = config.state;
		this._mouseHandlers = config.mouseHandlers;
		this._timeProjector = config.timeProjector ?? new TimeProjector();
		this._paneView = config.paneView;
		this._paneViews = [config.paneView];
	}

	public attached({ chart, series, requestUpdate }: SeriesAttachedParameter<Time>): void {
		this._chart = chart;
		this._series = series;
		this._requestUpdate = requestUpdate;

		this._timeProjector.attach(chart);
		this._mouseHandlers.attached(chart, series, this._timeProjector);
		this._mouseHandlers.setDrawingMode(this._state.isDrawingMode());

		this._subscribe(this._state.drawingModeChanged(), (isDrawing) => {
			this._mouseHandlers.setDrawingMode(isDrawing);
			this._requestUpdate?.();
		});

		this._subscribeToUpdate(this._mouseHandlers.mouseMoved());

		this._subscribe(this._mouseHandlers.pointHovered(), (target) => {
			this._state.setHoveredPoint(target);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.dragStarted(), (target) => {
			this._state.setDraggingPoint(target);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.dragEnded(), () => {
			this._state.setDraggingPoint(null);
			this._requestUpdate?.();
		});

		this._subscribe(this._mouseHandlers.chartClicked(), (clickEvent) => {
			if (this._state.isDrawingMode()) {
				this._state.addPoint({
					time: clickEvent.time,
					price: clickEvent.price
				});
				this._requestUpdate?.();
			}
		});

		this._setupSubscriptions();

		this._requestUpdate?.();
	}

	public detached(): void {
		for (const sub of this._trackedSubscriptions) {
			sub.unsubscribeAll(this);
		}
		this._trackedSubscriptions.clear();

		this._mouseHandlers.detached();
		this._chart = undefined;
		this._series = undefined;
		this._requestUpdate = undefined;
	}

	protected _subscribe<T>(delegate: ISubscription<T>, callback: (param: T) => void): void {
		this._trackedSubscriptions.add(delegate as ISubscription<unknown>);
		delegate.subscribe(callback, this);
	}

	protected _subscribeToUpdate<T>(delegate: ISubscription<T>): void {
		this._subscribe(delegate, () => {
			this._requestUpdate?.();
		});
	}

	public paneViews(): readonly IPrimitivePaneView[] {
		return this._paneViews;
	}

	public updateAllViews(): void {
		if (!this._chart || !this._series) {
			this._paneView.update(null);
			return;
		}

		const rendererData = this._calculateRendererData();
		this._updateCursor();
		this._paneView.update(rendererData);
	}

	public hitTest(): PrimitiveHoveredItem | null {
		if (!this._currentCursor) return null;
		return {
			cursorStyle: this._currentCursor,
			externalId: this._externalId,
			zOrder: 'top'
		};
	}

	protected _updateCursor(): void {
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

	public isDrawingMode(): boolean {
		return this._state.isDrawingMode();
	}

	public setDrawingMode(enabled: boolean): void {
		this._state.setDrawingMode(enabled);
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._state.drawingModeChanged();
	}

	public setCandles(candles: Candle[]): void {
		this._timeProjector.updateCandles(candles);
		this._requestUpdate?.();
	}

	public destroy(): void {
		this.detached();
		this._state.destroy();
	}

	protected _setupSubscriptions(): void {}

	protected abstract _calculateRendererData(): TRendererData | null;
}
