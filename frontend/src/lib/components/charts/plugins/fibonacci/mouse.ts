import type { ISeriesApi, SeriesType } from 'lightweight-charts';
import type { FibPoint, FibToolType } from '$lib/utils/finance/fibonacci';
import type { Candle } from '$lib/utils/finance/candle';
import { HIT_TEST_RADIUS } from './constants';
import { buildCandleLookup, findCandleByTime, snapPriceToWick } from '../helpers/mouse/snap';
import type { FibPointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';
import type { MousePosition } from '../helpers/mouse/mouse-position';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedFibPointWithTarget {
	tool: FibToolType;
	pointIndex: 0 | 1 | 2;
	x: number;
	y: number;
	originalPoint: FibPoint;
}

export interface ProjectedFibLine {
	tool: FibToolType;
	xStart: number;
	xEnd: number;
	y: number;
}

/**
 * Thin fibonacci adapter over the shared {@link ChartMouseHandlers}. Keeps the
 * plugin's public `MouseHandlers` surface (zero-arg constructor included);
 * snap-to-wicks state stays plugin-local and is injected through the shared
 * `adjustPosition` hook.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedFibPointWithTarget,
	FibPointTarget,
	FibPoint
> {
	private _candleLookup: Map<number, Candle> = new Map();
	private _projectedLines: ProjectedFibLine[] = [];

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ tool: p.tool, pointIndex: p.pointIndex }),
			adjustPosition: (pos, series) => this._adjustPosition(pos, series),
			hitTestLine: (x, y) => {
				const hit = this.hitTestLine(x, y);
				return hit ? { tool: hit.tool, pointIndex: 0 } : null;
			}
		});
	}

	public setProjectedLines(lines: ProjectedFibLine[]): void {
		this._projectedLines = lines;
	}

	public hitTestLine(x: number, y: number): ProjectedFibLine | null {
		let closestLine: ProjectedFibLine | null = null;
		let closestDist = Infinity;

		for (const line of this._projectedLines) {
			const minX = Math.min(line.xStart, line.xEnd);
			const maxX = Math.max(line.xStart, line.xEnd);
			const clampX = Math.max(minX, Math.min(x, maxX));
			const dist = Math.hypot(x - clampX, y - line.y);
			if (dist <= HIT_TEST_RADIUS && dist < closestDist) {
				closestDist = dist;
				closestLine = line;
			}
		}

		return closestLine;
	}

	public override detached(): void {
		super.detached();
		this._projectedLines = [];
	}

	private _adjustPosition(pos: MousePosition, series: ISeriesApi<SeriesType>) {
		const candle = findCandleByTime(this._candleLookup, pos.time);
		if (!candle) return { price: pos.price as number, y: pos.y, snapped: false };
		const price = snapPriceToWick(pos.price as number, candle);
		const snappedY = series.priceToCoordinate(price);
		return { price, y: snappedY !== null ? snappedY : pos.y, snapped: true };
	}

	public adjustPosition(
		pos: MousePosition,
		series: ISeriesApi<SeriesType>
	): { price: number; y: number; snapped: boolean } {
		return this._adjustPosition(pos, series);
	}

	public setCandles(candles: Candle[]): void {
		this._candleLookup = buildCandleLookup(candles);
	}
}
