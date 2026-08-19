import type { Time } from 'lightweight-charts';
import type { Candle } from './candle';
import { parseCandleTime } from '$lib/chart-preferences';

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

/**
 * Returns a YYYY-MM-DD string representation of a Date in local time.
 */
export function getDayKey(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

/**
 * Returns a YYYY-MM-DD string of the Monday anchoring the ISO week for a given Date.
 */
export function getWeekKey(date: Date): string {
	const dayOfWeek = date.getDay();
	// ISO week: Monday is day 1, Sunday is day 7 (getDay() returns 0 for Sunday)
	const dayShift = (dayOfWeek + 6) % 7;
	const monday = new Date(date.getFullYear(), date.getMonth(), date.getDate() - dayShift);
	const year = monday.getFullYear();
	const month = String(monday.getMonth() + 1).padStart(2, '0');
	const day = String(monday.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

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
 * Aggregates candles into calendar-based groups (days or weeks), calculates SMA across
 * the group close prices, and projects the calculated MA values onto each candle in the group.
 */
function calculateGroupedMA(
	candles: Candle[],
	period: number,
	getKey: (date: Date) => string
): MASeries {
	if (!candles || candles.length === 0 || period <= 0) {
		return [];
	}

	interface Group {
		key: string;
		candles: Candle[];
		close: number;
	}

	const groups: Group[] = [];
	let currentGroup: Group | null = null;

	for (const candle of candles) {
		const date = parseCandleTime(candle.time);
		const key = getKey(date);

		if (!currentGroup || currentGroup.key !== key) {
			currentGroup = {
				key,
				candles: [candle],
				close: candle.close
			};
			groups.push(currentGroup);
		} else {
			currentGroup.candles.push(candle);
			currentGroup.close = candle.close;
		}
	}

	if (groups.length < period) {
		return [];
	}

	const result: MASeries = [];

	for (let i = period - 1; i < groups.length; i++) {
		let sum = 0;
		for (let j = 0; j < period; j++) {
			sum += groups[i - j].close;
		}
		const maValue = sum / period;

		for (const candle of groups[i].candles) {
			result.push({
				time: candle.time,
				value: maValue
			});
		}
	}

	return result;
}

/**
 * Calculates moving averages adapted to any target chart timeframe (1h, 4h, 1d, 1w, 1m).
 * Uses calendar-based aggregation for sub-unit intervals (e.g. projecting daily closes onto 1h bars)
 * and scaled periods for super-unit intervals (e.g. 50-day MA on 1w charts).
 */
export function calculateTimeframeMA(candles: Candle[], options: TimeframeMAOptions): MASeries {
	const { interval, period, unit = 'day' } = options;

	if (!candles || candles.length === 0 || !period || period <= 0) {
		return [];
	}

	const normInterval = (interval ?? '').toLowerCase();

	if (unit === 'week') {
		switch (normInterval) {
			case '1h':
			case '4h':
			case '1d':
				return calculateGroupedMA(candles, period, getWeekKey);
			case '1w':
				return calculateSMA(candles, period);
			case '1m':
				return calculateSMA(candles, Math.max(1, Math.round((period * 12) / 52)));
			default:
				if (
					normInterval.endsWith('h') ||
					(normInterval.endsWith('m') && normInterval !== '1m') ||
					normInterval.endsWith('s')
				) {
					return calculateGroupedMA(candles, period, getWeekKey);
				}
				return calculateSMA(candles, period);
		}
	}

	// Default: unit === 'day'
	switch (normInterval) {
		case '1h':
		case '4h':
			return calculateGroupedMA(candles, period, getDayKey);
		case '1d':
			return calculateSMA(candles, period);
		case '1w':
			return calculateSMA(candles, Math.max(1, Math.round(period / 5)));
		case '1m':
			return calculateSMA(candles, Math.max(1, Math.round(period / 21)));
		default:
			if (
				normInterval.endsWith('h') ||
				(normInterval.endsWith('m') && normInterval !== '1m') ||
				normInterval.endsWith('s')
			) {
				return calculateGroupedMA(candles, period, getDayKey);
			}
			return calculateSMA(candles, period);
	}
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
