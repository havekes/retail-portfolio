import type { ISeriesApi, SeriesType } from 'lightweight-charts';
import type { WaveDegree, WavePoint } from '$lib/utils/finance/elliott-wave';
import type { Candle } from '$lib/utils/finance/candle';
import { HIT_TEST_RADIUS } from './constants';
import { buildCandleLookup, findCandleByTime, snapPriceToWick } from '../helpers/mouse/snap';
import type { PointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';
import type { MousePosition } from '../helpers/mouse/mouse-position';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedPointWithTarget {
	degree: WaveDegree;
	wave: 0 | 1 | 2 | 3 | 4 | 5;
	x: number;
	y: number;
	originalPoint: WavePoint;
}

/**
 * Thin elliott-wave adapter over the shared {@link ChartMouseHandlers}. Keeps the
 * plugin's public `MouseHandlers` surface (zero-arg constructor included);
 * snap-to-wicks state stays plugin-local and is injected through the shared
 * `adjustPosition` hook.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedPointWithTarget,
	PointTarget,
	WavePoint
> {
	private _snapToWicks: boolean = false;
	private _candleLookup: Map<number, Candle> = new Map();

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ degree: p.degree, wave: p.wave }),
			adjustPosition: (pos, series) => this._adjustPosition(pos, series)
		});
	}

	// Only invoked by the shared handler when pos.price is non-null.
	private _adjustPosition(pos: MousePosition, series: ISeriesApi<SeriesType>) {
		if (!this._snapToWicks) return { price: pos.price as number, y: pos.y };
		const candle = findCandleByTime(this._candleLookup, pos.time);
		if (!candle) return { price: pos.price as number, y: pos.y };
		const price = snapPriceToWick(pos.price as number, candle);
		const snappedY = series.priceToCoordinate(price);
		return { price, y: snappedY !== null ? snappedY : pos.y };
	}

	public setSnapToWicks(enabled: boolean): void {
		this._snapToWicks = enabled;
	}

	public getSnapToWicks(): boolean {
		return this._snapToWicks;
	}

	public setCandles(candles: Candle[]): void {
		this._candleLookup = buildCandleLookup(candles);
	}
}
