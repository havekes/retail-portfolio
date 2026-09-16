import type { Time } from 'lightweight-charts';
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
	time: Time;
	middle: number;
	upper: number;
	lower: number;
};

export type BBSeries = BBValue[];
