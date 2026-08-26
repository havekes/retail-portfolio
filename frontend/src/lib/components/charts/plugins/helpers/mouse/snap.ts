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
