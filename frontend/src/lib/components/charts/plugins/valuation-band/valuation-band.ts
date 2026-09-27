import type {
	ISeriesPrimitive,
	IPrimitivePaneView,
	IPrimitivePaneRenderer,
	SeriesAttachedParameter,
	Time,
	SeriesType,
	ISeriesApi,
	IChartApi
} from 'lightweight-charts';

interface BitmapScope {
	context: CanvasRenderingContext2D;
	horizontalPixelRatio: number;
	verticalPixelRatio: number;
}

export interface CanvasTarget {
	useBitmapCoordinateSpace: (cb: (scope: BitmapScope) => void) => void;
}

export class ValuationBandPrimitive implements ISeriesPrimitive {
	private _paneView: ValuationBandPaneView;
	private _requestUpdate?: () => void;

	constructor(
		lower: number | null = null,
		upper: number | null = null,
		visible = true,
		color = 'rgba(59, 130, 246, 0.12)'
	) {
		this._paneView = new ValuationBandPaneView(lower, upper, visible, color);
	}

	attached(param: SeriesAttachedParameter<Time, SeriesType>) {
		this._requestUpdate = param.requestUpdate;
		this._paneView.attach(param.chart, param.series);
		param.requestUpdate();
	}

	detached() {
		this._paneView.detach();
		this._requestUpdate = undefined;
	}

	paneViews() {
		return [this._paneView];
	}

	updateAllViews() {
		this._paneView.update();
	}

	setRange(lower: number | null, upper: number | null, visible = true) {
		this._paneView.setRange(lower, upper, visible);
		this._requestUpdate?.();
	}
}

export class ValuationBandPaneView implements IPrimitivePaneView {
	private _chart: IChartApi | null = null;
	private _series: ISeriesApi<SeriesType> | null = null;
	private _lower: number | null;
	private _upper: number | null;
	private _visible: boolean;
	private _color: string;

	constructor(lower: number | null, upper: number | null, visible: boolean, color: string) {
		this._lower = lower;
		this._upper = upper;
		this._visible = visible;
		this._color = color;
	}

	attach(chart: IChartApi, series: ISeriesApi<SeriesType>) {
		this._chart = chart;
		this._series = series;
	}

	detach() {
		this._chart = null;
		this._series = null;
	}

	update() {}

	setRange(lower: number | null, upper: number | null, visible: boolean) {
		this._lower = lower;
		this._upper = upper;
		this._visible = visible;
	}

	renderer() {
		return new ValuationBandRenderer(
			this._lower,
			this._upper,
			this._visible,
			this._color,
			this._series
		);
	}

	zOrder(): 'bottom' | 'normal' | 'top' {
		return 'bottom';
	}
}

export class ValuationBandRenderer implements IPrimitivePaneRenderer {
	private _lower: number | null;
	private _upper: number | null;
	private _visible: boolean;
	private _color: string;
	private _series: ISeriesApi<SeriesType> | null;

	constructor(
		lower: number | null,
		upper: number | null,
		visible: boolean,
		color: string,
		series: ISeriesApi<SeriesType> | null
	) {
		this._lower = lower;
		this._upper = upper;
		this._visible = visible;
		this._color = color;
		this._series = series;
	}

	draw(target: CanvasTarget) {
		if (!this._visible || this._lower == null || this._upper == null || !this._series) {
			return;
		}

		target.useBitmapCoordinateSpace((scope) => {
			const { context, horizontalPixelRatio, verticalPixelRatio } = scope;
			const y1 = this._series?.priceToCoordinate(this._upper!);
			const y2 = this._series?.priceToCoordinate(this._lower!);

			if (y1 == null || y2 == null) return;

			const top = Math.min(y1, y2) * verticalPixelRatio;
			const height = Math.abs(y2 - y1) * verticalPixelRatio;
			const width = context.canvas.width;

			context.save();
			context.fillStyle = this._color;
			context.fillRect(0, top, width, height);

			context.strokeStyle = 'rgba(59, 130, 246, 0.4)';
			context.lineWidth = 1 * verticalPixelRatio;
			context.setLineDash([4 * horizontalPixelRatio, 4 * horizontalPixelRatio]);
			context.beginPath();
			context.moveTo(0, y1 * verticalPixelRatio);
			context.lineTo(width, y1 * verticalPixelRatio);
			context.moveTo(0, y2 * verticalPixelRatio);
			context.lineTo(width, y2 * verticalPixelRatio);
			context.stroke();

			context.restore();
		});
	}
}
