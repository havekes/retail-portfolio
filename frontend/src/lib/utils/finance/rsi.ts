import type { Candle } from './candle';
import type { IndicatorConfig, IndicatorSettings } from '@/api/indicatorsService';

export type RSISettings = IndicatorSettings & {
	period: number;
};

export type RsiConfig = IndicatorConfig & {
	settings: RSISettings;
};

export const defaultRSIConfig: RsiConfig = {
	enabled: false,
	color: '#06b6d4',
	settings: {
		period: 14
	}
};

export type RSIValue = {
	time: string;
	value: number;
};

export type RSISeries = RSIValue[];

export function calculateRSI(data: Candle[], settings: RSISettings): RSISeries {
	const period = settings.period;

	if (data.length <= period) {
		return [];
	}

	const rsiData: RSISeries = [];
	let avgGain = 0;
	let avgLoss = 0;

	for (let i = 1; i <= period; i++) {
		const diff = data[i].close - data[i - 1].close;
		if (diff >= 0) {
			avgGain += diff;
		} else {
			avgLoss -= diff;
		}
	}
	avgGain /= period;
	avgLoss /= period;

	let rs = avgLoss === 0 ? 0 : avgGain / avgLoss;
	let rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
	rsiData.push({ time: data[period].time, value: rsi });

	for (let i = period + 1; i < data.length; i++) {
		const diff = data[i].close - data[i - 1].close;
		let gain = 0;
		let loss = 0;
		if (diff >= 0) {
			gain = diff;
		} else {
			loss = -diff;
		}

		avgGain = (avgGain * (period - 1) + gain) / period;
		avgLoss = (avgLoss * (period - 1) + loss) / period;

		rs = avgLoss === 0 ? 0 : avgGain / avgLoss;
		rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
		rsiData.push({ time: data[i].time, value: rsi });
	}
	return rsiData;
}
