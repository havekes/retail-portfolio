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

export interface BandData {
	time: string;
	upper: number;
	lower: number;
}

export class BandsIndicator implements ISeriesPrimitive {
	private _paneView: BandPaneView;

	constructor(data: BandData[], color: string) {
		this._paneView = new BandPaneView(data, color);
	}

	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	attached(param: SeriesAttachedParameter<Time, SeriesType>) {
		this._paneView.attach(param.chart, param.series);
		param.requestUpdate();
	}

	detached() {
		this._paneView.detach();
	}

	paneViews() {
		return [this._paneView];
	}

	updateAllViews() {
		this._paneView.update();
	}
}

class BandPaneView implements IPrimitivePaneView {
	private _chart: IChartApi | null = null;
	private _series: ISeriesApi<SeriesType> | null = null;
	private _data: BandData[];
	private _color: string;

	constructor(data: BandData[], color: string) {
		this._data = data;
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

	renderer() {
		return new BandRenderer(this._data, this._color, this._chart, this._series);
	}

	zOrder(): 'bottom' | 'normal' | 'top' {
		return 'bottom';
	}
}

class BandRenderer implements IPrimitivePaneRenderer {
	private _data: BandData[];
	private _color: string;
	private _chart: IChartApi | null;
	private _series: ISeriesApi<SeriesType> | null;

	constructor(
		data: BandData[],
		color: string,
		chart: IChartApi | null,
		series: ISeriesApi<SeriesType> | null
	) {
		this._data = data;
		this._color = color;
		this._chart = chart;
		this._series = series;
	}

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	draw(target: any) {
		if (!this._chart || !this._series || this._data.length === 0) return;

		target.useBitmapCoordinateSpace((scope: any) => {
			const ctx = scope.context;
			const timeScale = this._chart!.timeScale();
			let started = false;

			ctx.beginPath();

			// Draw upper edge, left to right
			for (const item of this._data) {
				const x = timeScale.timeToCoordinate(item.time as unknown as Time);
				if (x === null) continue;
				const top = this._series!.priceToCoordinate(item.upper);
				if (top === null) continue;

				const px = Math.round(x * scope.horizontalPixelRatio);
				const py = Math.round(top * scope.verticalPixelRatio);

				if (!started) {
					ctx.moveTo(px, py);
					started = true;
				} else {
					ctx.lineTo(px, py);
				}
			}

			// Draw lower edge, right to left to complete the polygon
			for (let i = this._data.length - 1; i >= 0; i--) {
				const item = this._data[i];
				const x = timeScale.timeToCoordinate(item.time as unknown as Time);
				if (x === null) continue;
				const bottom = this._series!.priceToCoordinate(item.lower);
				if (bottom === null) continue;

				const px = Math.round(x * scope.horizontalPixelRatio);
				const py = Math.round(bottom * scope.verticalPixelRatio);

				ctx.lineTo(px, py);
			}

			ctx.fillStyle = this._color;
			ctx.fill();
		});
	}
}
