import type { Candle } from './candle';
import type { IndicatorConfig, IndicatorSettings } from '@/api/indicatorsService';

export type BBSettings = IndicatorSettings & {
	period: number;
	stdDev: number;
};

export type BBConfig = IndicatorConfig & {
	settings: BBSettings;
};

export const defaultBBConfig: BBConfig = {
	enabled: false,
	color: '#8b5cf6',
	settings: {
		period: 20,
		stdDev: 2
	}
};

export type BBValue = {
	time: string;
	middle: number;
	upper: number;
	lower: number;
};

export type BBSeries = BBValue[];

export function calculateBollingerBands(data: Candle[], settings: BBSettings): BBSeries {
	const { period, stdDev: stdDevMultiplier } = settings;
	const bbData: BBSeries = [];

	if (data.length < period) {
		return [];
	}

	for (let i = period - 1; i < data.length; i++) {
		let sum = 0;
		for (let j = 0; j < period; j++) {
			sum += data[i - j].close;
		}
		const sma = sum / period;

		let sumSq = 0;
		for (let j = 0; j < period; j++) {
			const variance = data[i - j].close - sma;
			sumSq += variance * variance;
		}
		const stdDev = Math.sqrt(sumSq / period);

		bbData.push({
			time: data[i].time,
			middle: sma,
			upper: sma + stdDev * stdDevMultiplier,
			lower: sma - stdDev * stdDevMultiplier
		});
	}
	return bbData;
}
