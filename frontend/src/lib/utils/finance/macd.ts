import type { Candle } from './candle';
import { calculateEMA } from './moving-average';
import type { IndicatorConfig, IndicatorSettings } from '@/services/indicatorsService';

export type MACDSettings = IndicatorSettings & {
	fast: number;
	slow: number;
	signal: number;
};

export type MACDConfig = IndicatorConfig & {
	settings: MACDSettings;
};

export const defaultMACDConfig: MACDConfig = {
	enabled: false,
	color: '#ef4444',
	settings: {
		fast: 12,
		slow: 26,
		signal: 9
	}
};

export type MACDValue = {
	time: string;
	macd: number;
	signal: number;
	histogram: number;
};

export type MACDSeries = MACDValue[];

export function calculateMACD(data: Candle[], settings: MACDSettings): MACDSeries {
	const { fast, slow, signal } = settings;

	if (data.length <= slow) {
		return [];
	}
	const macdData: MACDSeries = [];
	const fastEma = calculateEMA(data, fast);
	const slowEma = calculateEMA(data, slow);
	const macdLine: number[] = new Array(data.length);
	const signalData: number[] = new Array(data.length);

	let count = 0;
	let sum = 0;
	for (let i = 0; i < data.length; i++) {
		if (fastEma[i] !== undefined && slowEma[i] !== undefined) {
			macdLine[i] = fastEma[i] - slowEma[i];
		}
	}

	const multiplier = 2 / (signal + 1);
	let firstSignalIndex = -1;
	for (let i = 0; i < data.length; i++) {
		if (macdLine[i] !== undefined) {
			if (firstSignalIndex === -1 && count < signal) {
				sum += macdLine[i];
				count++;
				if (count === signal) {
					firstSignalIndex = i;
					signalData[i] = sum / signal;
				}
			} else if (firstSignalIndex !== -1) {
				signalData[i] = (macdLine[i] - signalData[i - 1]) * multiplier + signalData[i - 1];
			}
		}
	}

	for (let i = 0; i < data.length; i++) {
		if (signalData[i] !== undefined) {
			macdData.push({
				time: data[i].time,
				macd: macdLine[i],
				signal: signalData[i],
				histogram: macdLine[i] - signalData[i]
			});
		}
	}

	return macdData;
}
