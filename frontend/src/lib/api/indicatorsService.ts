import { ApiClient } from './apiClient';

export interface IndicatorConfig {
	enabled: boolean;
	color: string;
	settings: IndicatorSettings;
}

export interface IndicatorSettings {
	[key: string]: unknown;
}

export interface IndicatorPreferences {
	security_id: string;
	user_id: string;
	indicators: Record<string, IndicatorConfig>;
	updated_at?: string;
}

export interface IndicatorData {
	type: string;
	label: string;
	color: string;
	data: { time: string; value: number }[];
}

export class IndicatorsService extends ApiClient {
	async getPreferences(securityId: string): Promise<IndicatorPreferences> {
		return await this.get<IndicatorPreferences>(`/securities/${securityId}/indicator-preferences`);
	}

	async savePreferences(
		securityId: string,
		preferences: Omit<IndicatorPreferences, 'updated_at'>
	): Promise<IndicatorPreferences> {
		return await this.patch<IndicatorPreferences, typeof preferences>(
			`/securities/${securityId}/indicator-preferences`,
			preferences
		);
	}

	async getIndicatorData(securityId: string, indicatorType: string): Promise<IndicatorData> {
		return await this.get<IndicatorData>(
			`/securities/${securityId}/indicators?type=${indicatorType}`
		);
	}

	async getAllIndicatorData(securityId: string): Promise<IndicatorData[]> {
		return await this.get<IndicatorData[]>(`/securities/${securityId}/indicators`);
	}
}

export const indicatorsService = new IndicatorsService();
