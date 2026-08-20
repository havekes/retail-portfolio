import type { Time } from 'lightweight-charts';
import type { Candle } from './candle';

export type HoldingsPeriod = '1D' | '1W' | '1M' | '1Y' | 'YTD' | 'ALL';

export interface HoldingGain {
	gainAmount: number;
	gainPercent: number;
}

/**
 * Parses various lightweight-charts Time formats (number, UTCTimestamp, string, BusinessDay) into a JavaScript Date.
 */
export function parseCandleTimeToDate(time: Time | number): Date {
	if (typeof time === 'number') {
		return new Date(time * 1000);
	}
	if (typeof time === 'string') {
		if (/^\d{4}-\d{2}-\d{2}$/.test(time)) {
			const [year, month, day] = time.split('-').map(Number);
			return new Date(year, month - 1, day);
		}
		return new Date(time);
	}
	if (
		typeof time === 'object' &&
		time !== null &&
		'year' in time &&
		'month' in time &&
		'day' in time
	) {
		return new Date(time.year, time.month - 1, time.day);
	}
	return new Date(String(time));
}

/**
 * Calculates the starting cutoff date for a given holdings timeframe.
 * Returns null for 'ALL' since it encompasses all available history.
 */
export function getPeriodCutoffDate(
	period: HoldingsPeriod,
	referenceDate: Date = new Date()
): Date | null {
	const ref = new Date(referenceDate);
	switch (period) {
		case '1D': {
			const d = new Date(ref);
			d.setDate(d.getDate() - 1);
			d.setHours(0, 0, 0, 0);
			return d;
		}
		case '1W': {
			const d = new Date(ref);
			d.setDate(d.getDate() - 7);
			d.setHours(0, 0, 0, 0);
			return d;
		}
		case '1M': {
			const d = new Date(ref);
			d.setMonth(d.getMonth() - 1);
			d.setHours(0, 0, 0, 0);
			return d;
		}
		case '1Y': {
			const d = new Date(ref);
			d.setFullYear(d.getFullYear() - 1);
			d.setHours(0, 0, 0, 0);
			return d;
		}
		case 'YTD': {
			return new Date(ref.getFullYear(), 0, 1, 0, 0, 0, 0);
		}
		case 'ALL':
			return null;
		default:
			return null;
	}
}

/**
 * Resolves the baseline benchmark price for a given period:
 * - 'ALL': resolves average cost basis.
 * - '1D' | '1W' | '1M' | '1Y' | 'YTD': resolves the close price of the most recent candle
 *   on or before the timeframe cutoff date (or earliest available candle if none precedes cutoff).
 */
export function getBenchmarkPrice(
	candles: Candle[],
	period: HoldingsPeriod,
	averageCost?: number | null,
	referenceDate?: Date
): number | null {
	if (period === 'ALL') {
		if (typeof averageCost === 'number' && !isNaN(averageCost)) {
			return averageCost;
		}
		return null;
	}

	if (!candles || candles.length === 0) {
		return null;
	}

	const cutoff = getPeriodCutoffDate(period, referenceDate);
	if (!cutoff) {
		return candles[0].close;
	}

	const cutoffTime = cutoff.getTime();

	let bestBeforeCutoff: { candle: Candle; time: number } | null = null;
	let earliestCandle: { candle: Candle; time: number } | null = null;

	for (const candle of candles) {
		const time = parseCandleTimeToDate(candle.time).getTime();
		if (!earliestCandle || time < earliestCandle.time) {
			earliestCandle = { candle, time };
		}
		if (time <= cutoffTime) {
			if (!bestBeforeCutoff || time > bestBeforeCutoff.time) {
				bestBeforeCutoff = { candle, time };
			}
		}
	}

	if (bestBeforeCutoff) {
		return bestBeforeCutoff.candle.close;
	}

	return earliestCandle ? earliestCandle.candle.close : candles[0].close;
}

/**
 * Calculates profit/loss gain amount and gain percentage against a benchmark price.
 */
export function calculateHoldingGain(
	currentPrice: number,
	benchmarkPrice: number,
	quantity: number
): HoldingGain {
	if (
		typeof currentPrice !== 'number' ||
		isNaN(currentPrice) ||
		typeof benchmarkPrice !== 'number' ||
		isNaN(benchmarkPrice) ||
		typeof quantity !== 'number' ||
		isNaN(quantity)
	) {
		return { gainAmount: 0, gainPercent: 0 };
	}

	const priceDiff = currentPrice - benchmarkPrice;
	const gainAmount = priceDiff * quantity;
	const gainPercent = benchmarkPrice !== 0 ? (priceDiff / benchmarkPrice) * 100 : 0;

	return {
		gainAmount,
		gainPercent
	};
}

/**
 * Filters an array of candles to include only those on or after the timeframe cutoff date.
 * Returns all candles for 'ALL'.
 */
export function filterCandlesForPeriod(
	candles: Candle[],
	period: HoldingsPeriod,
	referenceDate?: Date
): Candle[] {
	if (!candles || candles.length === 0) {
		return [];
	}
	if (period === 'ALL') {
		return [...candles];
	}
	const cutoff = getPeriodCutoffDate(period, referenceDate);
	if (!cutoff) {
		return [...candles];
	}
	const cutoffTime = cutoff.getTime();
	return candles.filter((c) => parseCandleTimeToDate(c.time).getTime() >= cutoffTime);
}
