import { ApiClient } from './apiClient';

export interface IndicatorConfig {
	enabled: boolean;
	color: string;
	settings: IndicatorSettings;
}

export interface IndicatorSettings {
	[key: string]: unknown;
}

export interface IndicatorData {
	type: string;
	label: string;
	color: string;
	data: { time: string; value: number }[];
}

export class IndicatorsService extends ApiClient {
	async getIndicatorData(securityId: string, indicatorType: string): Promise<IndicatorData> {
		return await this.get<IndicatorData>(
			`/market/securities/${securityId}/indicators?type=${indicatorType}`
		);
	}

	async getAllIndicatorData(securityId: string): Promise<IndicatorData[]> {
		return await this.get<IndicatorData[]>(`/market/securities/${securityId}/indicators`);
	}
}

export const indicatorsService = new IndicatorsService();
