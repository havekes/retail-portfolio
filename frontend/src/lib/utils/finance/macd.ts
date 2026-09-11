import type { Time } from 'lightweight-charts';
import type { IndicatorConfig, IndicatorSettings } from '@/api/indicatorsService';

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
	time: Time;
	macd: number;
	signal: number;
	histogram: number;
};

export type MACDSeries = MACDValue[];
