import type { Time } from 'lightweight-charts';
import type { Candle } from './candle';

export type TimeframeMAUnit = 'day' | 'week';

export interface TimeframeMAOptions {
	interval: string;
	period: number;
	unit?: TimeframeMAUnit;
}

export type MAValue = {
	time: Time;
	value: number;
};

export type MASeries = MAValue[];

export function calculateSMA(data: Candle[], period: number): MASeries {
	if (!data || data.length < period || period <= 0) {
		return [];
	}
	const smaData: MASeries = [];
	for (let i = period - 1; i < data.length; i++) {
		let sum = 0;
		for (let j = 0; j < period; j++) {
			sum += data[i - j].close;
		}
		smaData.push({ time: data[i].time, value: sum / period });
	}
	return smaData;
}

export function calculateEMA(data: Candle[], period: number): number[] {
	if (!data || data.length < period || period <= 0) {
		return [];
	}
	const emaData = new Array<number>(data.length);
	const multiplier = 2 / (period + 1);

	let sum = 0;
	for (let i = 0; i < period; i++) {
		sum += data[i].close;
	}
	emaData[period - 1] = sum / period;

	for (let i = period; i < data.length; i++) {
		emaData[i] = (data[i].close - emaData[i - 1]) * multiplier + emaData[i - 1];
	}
	return emaData;
}

/**
 * Calculates continuous rolling moving averages adapted to target chart timeframes (1h, 4h, 1d, 1w, 1m).
 * Scales the target period into equivalent candle counts based on trading sessions:
 * - Day MAs (unit: 'day'): 1h -> period * 7, 4h -> period * 2, 1d -> period, 1w -> round(period / 5), 1m -> round(period / 21)
 * - Week MAs (unit: 'week'): 1h -> period * 35, 4h -> period * 10, 1d -> period * 5, 1w -> period, 1m -> round(period * 12 / 52)
 */
export function calculateTimeframeMA(candles: Candle[], options: TimeframeMAOptions): MASeries {
	const { interval, period, unit = 'day' } = options;

	if (!candles || candles.length === 0 || !period || period <= 0) {
		return [];
	}

	const normInterval = (interval ?? '').toLowerCase();
	let effectivePeriod: number;

	if (unit === 'week') {
		switch (normInterval) {
			case '1h':
				effectivePeriod = period * 35;
				break;
			case '4h':
				effectivePeriod = period * 10;
				break;
			case '1d':
				effectivePeriod = period * 5;
				break;
			case '1w':
				effectivePeriod = period;
				break;
			case '1m':
				effectivePeriod = Math.max(1, Math.round((period * 12) / 52));
				break;
			default:
				effectivePeriod = period;
				break;
		}
	} else {
		// Default: unit === 'day'
		switch (normInterval) {
			case '1h':
				effectivePeriod = period * 7;
				break;
			case '4h':
				effectivePeriod = period * 2;
				break;
			case '1d':
				effectivePeriod = period;
				break;
			case '1w':
				effectivePeriod = Math.max(1, Math.round(period / 5));
				break;
			case '1m':
				effectivePeriod = Math.max(1, Math.round(period / 21));
				break;
			default:
				effectivePeriod = period;
				break;
		}
	}

	return calculateSMA(candles, effectivePeriod);
}

export function calculateDayMA(candles: Candle[], interval: string, period: number): MASeries {
	return calculateTimeframeMA(candles, { interval, period, unit: 'day' });
}

export function calculateWeekMA(candles: Candle[], interval: string, period: number): MASeries {
	return calculateTimeframeMA(candles, { interval, period, unit: 'week' });
}

export function calculate50DayMA(candles: Candle[], interval: string): MASeries {
	return calculateDayMA(candles, interval, 50);
}

export function calculate200DayMA(candles: Candle[], interval: string): MASeries {
	return calculateDayMA(candles, interval, 200);
}

export function calculate50WeekMA(candles: Candle[], interval: string): MASeries {
	return calculateWeekMA(candles, interval, 50);
}

export function calculate200WeekMA(candles: Candle[], interval: string): MASeries {
	return calculateWeekMA(candles, interval, 200);
}
