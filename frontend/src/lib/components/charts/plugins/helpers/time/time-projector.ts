import type { IChartApi, Logical, Time, UTCTimestamp } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import {
	addIntervalToTime,
	barsBetweenTimes,
	computeIntervalSeconds,
	resolveAnchorEpoch,
	timeToEpochSeconds
} from './time';

/**
 * Projects chart coordinates <-> time both within historical data (via the
 * lightweight-charts time scale) and beyond the last data point (the "future"
 * area to the right of the last candle). Future timestamps are extrapolated
 * from the last candle's time plus whole bar intervals, and mapped back to x
 * coordinates using logical bar indices.
 *
 * Drawing anchors are canonical epoch seconds, so the projector also exposes
 * epoch-based resolution: an epoch is snapped to the active timeframe's candle
 * (at or before the anchor) before asking the time scale for a coordinate.
 */
export class TimeProjector {
	private _chart: IChartApi | undefined;
	private _candles: Candle[] = [];
	private _lastTime: Time | undefined;
	private _intervalSeconds: number = 0;
	private _lastDataIndex: number = -1;

	/** Bind the projector to a chart so it can resolve coordinates. */
	public attach(chart: IChartApi): void {
		this._chart = chart;
	}

	/** Recompute the reference time / interval from the latest candle data. */
	public updateCandles(candles: Candle[]): void {
		if (!candles || candles.length === 0) {
			this._candles = [];
			this._lastTime = undefined;
			this._intervalSeconds = 0;
			this._lastDataIndex = -1;
			return;
		}
		this._candles = candles;
		this._lastTime = candles[candles.length - 1].time;
		this._lastDataIndex = candles.length - 1;
		this._intervalSeconds = computeIntervalSeconds(candles);
	}

	public hasFutureProjection(): boolean {
		return this._lastTime !== undefined && this._intervalSeconds > 0;
	}

	/**
	 * Resolve an x coordinate to a Time. Returns the time scale's answer when
	 * within historical data; otherwise extrapolates beyond the last candle.
	 */
	public coordinateToTime(x: number): Time | null {
		if (!this._chart) return null;
		const ts = this._chart.timeScale();
		const resolved = ts.coordinateToTime(x);
		if (resolved !== null) return resolved;
		return this._extrapolateTimeFromLogical(x, ts);
	}

	/**
	 * Resolve an x coordinate to canonical epoch seconds. Returns null when the
	 * coordinate cannot be resolved (including when it is off the time scale).
	 */
	public coordinateToEpoch(x: number): number | null {
		const resolved = this.coordinateToTime(x);
		if (resolved === null) return null;
		return timeToEpochSeconds(resolved);
	}

	/**
	 * Resolve a Time to an x coordinate. Returns the time scale's answer when
	 * the time falls within historical data; otherwise extrapolates via the
	 * logical bar index for future timestamps.
	 */
	public timeToCoordinate(time: Time): number | null {
		if (!this._chart) return null;
		const ts = this._chart.timeScale();
		const resolved = ts.timeToCoordinate(time);
		if (resolved !== null) return resolved;
		if (!this.hasFutureProjection()) return null;

		const barsBeyond = barsBetweenTimes(this._lastTime!, time, this._intervalSeconds);
		if (barsBeyond <= 0) return null;

		return this._logicalToCoordinate(this._lastDataIndex + barsBeyond, ts);
	}

	/**
	 * Resolve a canonical epoch-seconds anchor to an x coordinate on the active
	 * timeframe. The epoch is snapped to the candle at or before it (clamped to
	 * the first candle), which maps the same drawing date onto the containing
	 * bar of every timeframe. Anchors beyond the last candle reuse the future
	 * projection path.
	 */
	public epochToCoordinate(epoch: number): number | null {
		if (!this._chart) return null;
		if (!Number.isFinite(epoch)) return null;
		const ts = this._chart.timeScale();

		if (this._candles.length > 0) {
			const snapped = resolveAnchorEpoch(this._candles, epoch);
			if (snapped !== null) {
				const resolved = ts.timeToCoordinate(snapped.time);
				if (resolved !== null && resolved !== undefined) return resolved;
			}
		} else {
			// No candle data retained: fall back to the time scale's own lookup.
			const resolved = ts.timeToCoordinate(epoch as UTCTimestamp);
			if (resolved !== null && resolved !== undefined) return resolved;
		}

		if (!this.hasFutureProjection()) return null;

		const barsBeyond = barsBetweenTimes(this._lastTime!, epoch, this._intervalSeconds);
		if (barsBeyond <= 0) return null;

		return this._logicalToCoordinate(this._lastDataIndex + barsBeyond, ts);
	}

	private _extrapolateTimeFromLogical(
		x: number,
		ts: ReturnType<IChartApi['timeScale']>
	): Time | null {
		if (!this.hasFutureProjection()) return null;
		if (typeof ts.coordinateToLogical !== 'function') return null;

		const logical = ts.coordinateToLogical(x);
		if (logical === null || logical === undefined) return null;

		const barsBeyond = logical - this._lastDataIndex;
		if (barsBeyond <= 0) return null;

		return addIntervalToTime(this._lastTime!, barsBeyond, this._intervalSeconds);
	}

	private _logicalToCoordinate(
		logical: number,
		ts: ReturnType<IChartApi['timeScale']>
	): number | null {
		if (typeof ts.logicalToCoordinate !== 'function') return null;
		const coord = ts.logicalToCoordinate(logical as Logical);
		return coord === null || coord === undefined ? null : coord;
	}
}
