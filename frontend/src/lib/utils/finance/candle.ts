import type { Time, UTCTimestamp } from 'lightweight-charts';
export interface Candle {
	time: Time;
	open: number;
	high: number;
	low: number;
	close: number;
	volume?: number;
}

/**
 * Calculates the split ratio from adjusted close and close prices.
 * Returns null if adjusted_close is missing, non-positive, or effectively equal to close.
 */
export function calculateSplitRatio(close: number, adjustedClose?: number | null): number | null {
	if (
		adjustedClose != null &&
		!isNaN(adjustedClose) &&
		adjustedClose > 0 &&
		close > 0 &&
		Math.abs(adjustedClose - close) > 1e-6
	) {
		return adjustedClose / close;
	}
	return null;
}

/**
 * Applies stock split adjustment to a candle's OHLC values.
 * When adjusted_close differs from close, calculates ratio = adjusted_close / close
 * and scales open, high, low, close accordingly.
 */
export function applySplitAdjustment<
	T extends {
		open: number;
		high: number;
		low: number;
		close: number;
		adjusted_close?: number | null;
	}
>(candle: T): { open: number; high: number; low: number; close: number } {
	const ratio = calculateSplitRatio(candle.close, candle.adjusted_close);
	if (ratio !== null) {
		return {
			open: candle.open * ratio,
			high: candle.high * ratio,
			low: candle.low * ratio,
			close:
				candle.adjusted_close != null && candle.adjusted_close > 0
					? candle.adjusted_close
					: candle.close * ratio
		};
	}
	return {
		open: candle.open,
		high: candle.high,
		low: candle.low,
		close: candle.close
	};
}

/**
 * Maps a market price item into a split-adjusted Candle object suitable for lightweight-charts.
 */
export function mapPriceToCandle(
	price: {
		date?: string | null;
		timestamp?: string | number | null;
		open: number | string;
		high: number | string;
		low: number | string;
		close: number | string;
		adjusted_close?: number | string | null;
		volume?: number | string | null;
	},
	isIntraday = false
): Candle {
	const timeVal: Time =
		isIntraday && price.timestamp
			? typeof price.timestamp === 'number'
				? (price.timestamp as UTCTimestamp)
				: (Math.floor(new Date(price.timestamp).getTime() / 1000) as UTCTimestamp)
			: ((price.date ?? '') as Time);

	const raw = {
		open: Number(price.open),
		high: Number(price.high),
		low: Number(price.low),
		close: Number(price.close),
		adjusted_close: price.adjusted_close != null ? Number(price.adjusted_close) : undefined
	};

	const adjusted = applySplitAdjustment(raw);

	return {
		time: timeVal,
		open: adjusted.open,
		high: adjusted.high,
		low: adjusted.low,
		close: adjusted.close,
		volume: price.volume != null ? Number(price.volume) : undefined
	};
}

/**
 * Transforms raw price items into split-adjusted continuous candles.
 */
export function transformToSplitAdjustedCandles(
	items: {
		time: Time;
		open: number;
		high: number;
		low: number;
		close: number;
		adjusted_close?: number | null;
		volume?: number;
	}[]
): Candle[] {
	return items.map((p) => {
		const adjusted = applySplitAdjustment(p);
		return {
			time: p.time,
			open: adjusted.open,
			high: adjusted.high,
			low: adjusted.low,
			close: adjusted.close,
			volume: p.volume
		};
	});
}

export function convertToHeikinAshi(candles: Candle[]): Candle[] {
	const result: Candle[] = [];

	for (let i = 0; i < candles.length; i++) {
		const candle = candles[i];

		if (i === 0) {
			// First candle: calculate initial HA values
			const haClose = (candle.open + candle.high + candle.low + candle.close) / 4;
			const haOpen = (candle.open + candle.close) / 2;
			result.push({
				time: candle.time,
				open: haOpen,
				close: haClose,
				high: Math.max(candle.high, haOpen, haClose),
				low: Math.min(candle.low, haOpen, haClose),
				volume: candle.volume
			});
			continue;
		}

		// Get previous HA candle
		const prevHA = result[i - 1];

		// Heikin Ashi formulas
		const haClose = (candle.open + candle.high + candle.low + candle.close) / 4;
		const haOpen = (prevHA.open + prevHA.close) / 2;
		const haHigh = Math.max(candle.high, haOpen, haClose);
		const haLow = Math.min(candle.low, haOpen, haClose);

		result.push({
			time: candle.time,
			open: haOpen,
			high: haHigh,
			low: haLow,
			close: haClose,
			volume: candle.volume
		});
	}

	return result;
}
