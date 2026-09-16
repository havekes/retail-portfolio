import type { ISeriesApi, SeriesType } from 'lightweight-charts';
import type { WaveDegree, WavePoint, WavePointId } from '$lib/utils/finance/elliott-wave';
import type { Candle } from '$lib/utils/finance/candle';
import { HIT_TEST_RADIUS, FIB_SNAP_TOLERANCE_PX } from './constants';
import {
	buildCandleLookup,
	findCandleByTime,
	findNearestLevel,
	snapPriceToWick
} from '../helpers/mouse/snap';
import type { PointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';
import type { MousePosition } from '../helpers/mouse/mouse-position';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedPointWithTarget {
	degree: WaveDegree;
	wave: WavePointId;
	waveId?: string;
	x: number;
	y: number;
	originalPoint: WavePoint;
}

export interface ProjectedWaveSegment {
	degree: WaveDegree;
	wave: WavePointId;
	waveId?: string;
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}

interface SnapCandidate {
	price: number;
	y: number;
	distance: number;
}

function distanceToSegment(
	px: number,
	py: number,
	x1: number,
	y1: number,
	x2: number,
	y2: number
): number {
	const dx = x2 - x1;
	const dy = y2 - y1;
	const lengthSq = dx * dx + dy * dy;
	const t =
		lengthSq === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lengthSq));
	return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

/**
 * Thin elliott-wave adapter over the shared {@link ChartMouseHandlers}. Keeps the
 * plugin's public `MouseHandlers` surface (zero-arg constructor included);
 * snap-to-wicks and snap-to-Fib-level state stay plugin-local and are injected
 * through the shared `adjustPosition` hook.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedPointWithTarget,
	PointTarget,
	WavePoint
> {
	private _snapToWicks: boolean = false;
	private _candleLookup: Map<number, Candle> = new Map();
	private _fibLevelPrices: number[] = [];
	private _projectedSegments: ProjectedWaveSegment[] = [];

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ degree: p.degree, wave: p.wave, waveId: p.waveId }),
			adjustPosition: (pos, series) => this.resolveAdjustedPosition(pos, series),
			hitTestLine: (x, y) => {
				const hit = this.hitTestLine(x, y);
				return hit ? { degree: hit.degree, wave: hit.wave, waveId: hit.waveId } : null;
			}
		});
	}

	public setProjectedSegments(segments: ProjectedWaveSegment[]): void {
		this._projectedSegments = segments;
	}

	/**
	 * Returns the projected wave segment closest to (x, y) within
	 * {@link HIT_TEST_RADIUS} in CSS pixel space, or null when none is hit.
	 */
	public hitTestLine(x: number, y: number): ProjectedWaveSegment | null {
		let closest: ProjectedWaveSegment | null = null;
		let closestDist = Infinity;

		for (const seg of this._projectedSegments) {
			const dist = distanceToSegment(x, y, seg.x1, seg.y1, seg.x2, seg.y2);
			if (dist <= HIT_TEST_RADIUS && dist < closestDist) {
				closestDist = dist;
				closest = seg;
			}
		}

		return closest;
	}

	public override detached(): void {
		super.detached();
		this._projectedSegments = [];
	}

	/**
	 * Resolves the snapped pointer position shared by placement clicks, drag moves, and the
	 * drawing-preview ghost. Builds a candle-wick candidate (only when `snapToWicks` is on and
	 * a candle exists at the pointer's time) and a Fib-level candidate (only when the nearest
	 * active level is within {@link FIB_SNAP_TOLERANCE_PX} in pixel space), then returns the
	 * closer one. Pixel-space ties go to the wick, preserving the pre-existing behaviour. Fib
	 * snapping is independent of the `snapToWicks` setting.
	 *
	 * Only invoked by the shared handler when `pos.price` is non-null.
	 */
	public resolveAdjustedPosition(
		pos: MousePosition,
		series: ISeriesApi<SeriesType>
	): { price: number; y: number; snapped: boolean } {
		const rawPrice = pos.price as number;

		let wick: SnapCandidate | null = null;
		if (this._snapToWicks) {
			const candle = findCandleByTime(this._candleLookup, pos.time);
			if (candle) {
				const price = snapPriceToWick(rawPrice, candle);
				const snappedY = series.priceToCoordinate(price);
				const y = snappedY !== null ? snappedY : pos.y;
				wick = { price, y, distance: Math.abs(y - pos.y) };
			}
		}

		let fib: SnapCandidate | null = null;
		if (this._fibLevelPrices.length > 0) {
			const level = findNearestLevel(rawPrice, this._fibLevelPrices);
			if (level !== null) {
				const levelY = series.priceToCoordinate(level);
				if (levelY !== null && Math.abs(levelY - pos.y) <= FIB_SNAP_TOLERANCE_PX) {
					fib = { price: level, y: levelY, distance: Math.abs(levelY - pos.y) };
				}
			}
		}

		if (wick && fib) {
			const winner = fib.distance < wick.distance ? fib : wick;
			return { price: winner.price, y: winner.y, snapped: true };
		}
		if (wick) return { price: wick.price, y: wick.y, snapped: true };
		if (fib) return { price: fib.price, y: fib.y, snapped: true };
		return { price: rawPrice, y: pos.y, snapped: false };
	}

	public setSnapToWicks(enabled: boolean): void {
		this._snapToWicks = enabled;
	}

	public getSnapToWicks(): boolean {
		return this._snapToWicks;
	}

	public setFibLevelPrices(prices: number[]): void {
		this._fibLevelPrices = Array.isArray(prices) ? [...prices] : [];
	}

	public getFibLevelPrices(): number[] {
		return [...this._fibLevelPrices];
	}

	public setCandles(candles: Candle[]): void {
		this._candleLookup = buildCandleLookup(candles);
	}
}
