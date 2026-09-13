import type { Time } from 'lightweight-charts';
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
	time: Time;
	value: number;
};

export type RSISeries = RSIValue[];
