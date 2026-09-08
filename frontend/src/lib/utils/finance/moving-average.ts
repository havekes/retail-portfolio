import type { Time } from 'lightweight-charts';

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
