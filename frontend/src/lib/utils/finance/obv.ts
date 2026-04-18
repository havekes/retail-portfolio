import type { Candle } from './candle';
import type { IndicatorConfig, IndicatorSettings } from '@/services/indicatorsService';

export type OBVSettings = IndicatorSettings;

export type OBVConfig = IndicatorConfig & {
	settings: OBVSettings;
};

export const defaultOBVConfig: OBVConfig = {
	enabled: false,
	color: '#f59e0b',
	settings: {}
};

export type OBVValue = {
	time: string;
	value: number;
};

export type OBVSeries = OBVValue[];

export function calculateOBV(data: Candle[]): OBVSeries {
	const obvData: OBVSeries = [];
	let obv = 0;
	for (let i = 0; i < data.length; i++) {
		if (i > 0) {
			if (data[i].close > data[i - 1].close) {
				obv += data[i].volume || 0;
			} else if (data[i].close < data[i - 1].close) {
				obv -= data[i].volume || 0;
			}
		} else {
			obv = data[i].volume || 0;
		}
		obvData.push({ time: data[i].time, value: obv });
	}
	return obvData;
}
