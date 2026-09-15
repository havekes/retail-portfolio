import type { Time } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import { timeToEpochSeconds } from '../time/time';

/**
 * Snaps a given price to the nearest wick (high or low) of a candle.
 * In the event of a tie (price is equidistant from high and low), resolves to candle.high.
 */
export function snapPriceToWick(price: number, candle: Candle): number {
	const distHigh = Math.abs(price - candle.high);
	const distLow = Math.abs(price - candle.low);
	return distHigh <= distLow ? candle.high : candle.low;
}

/**
 * Finds the price-space closest value in `levelPrices` to `price`. Non-finite candidates and
 * a non-finite `price` are ignored, and an empty list returns null. Pixel-space tolerance is
 * the caller's responsibility — this helper only resolves the nearest candidate.
 */
export function findNearestLevel(price: number, levelPrices: readonly number[]): number | null {
	if (typeof price !== 'number' || !isFinite(price) || !Array.isArray(levelPrices)) {
		return null;
	}

	let nearest: number | null = null;
	let nearestDistance = Infinity;
	for (const level of levelPrices) {
		if (typeof level !== 'number' || !isFinite(level)) continue;
		const distance = Math.abs(price - level);
		if (distance < nearestDistance) {
			nearestDistance = distance;
			nearest = level;
		}
	}

	return nearest;
}

/**
 * Builds an O(1) lookup map of candles keyed by their normalized epoch seconds.
 */
export function buildCandleLookup(candles: Candle[]): Map<number, Candle> {
	const lookup = new Map<number, Candle>();
	for (const candle of candles) {
		lookup.set(timeToEpochSeconds(candle.time), candle);
	}
	return lookup;
}

/**
 * Finds a candle in the lookup map matching the given Time value.
 */
export function findCandleByTime(
	lookup: Map<number, Candle>,
	time: Time | null | undefined
): Candle | undefined {
	if (!time) return undefined;
	return lookup.get(timeToEpochSeconds(time));
}
