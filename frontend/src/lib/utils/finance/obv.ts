import type { Time } from 'lightweight-charts';
import type { IndicatorConfig, IndicatorSettings } from '@/api/indicatorsService';

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
	time: Time;
	value: number;
};

export type OBVSeries = OBVValue[];
