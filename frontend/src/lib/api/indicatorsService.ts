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

export interface IndicatorSpec {
	id?: string;
	type: string;
	period?: number;
	fast?: number;
	slow?: number;
	signal?: number;
	stdDev?: number;
	settings?: Record<string, unknown>;
}

export interface IndicatorCandle {
	time: number | string;
	open: number;
	high: number;
	low: number;
	close: number;
	volume?: number;
}

export interface IndicatorComputeRequest {
	interval: string;
	chart_style?: 'candlestick' | 'heikin_ashi';
	indicators: IndicatorSpec[];
	candles?: IndicatorCandle[];
	from_date?: string;
	to_date?: string;
}

export interface IndicatorComputeResponse {
	indicators: Record<string, unknown[]>;
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

	async computeIndicators(
		securityId: string,
		request: IndicatorComputeRequest
	): Promise<IndicatorComputeResponse> {
		return await this.post<IndicatorComputeResponse, IndicatorComputeRequest>(
			`/market/securities/${securityId}/indicators/compute`,
			request
		);
	}
}

export const getIndicatorsService = (customFetch?: typeof fetch) =>
	new IndicatorsService(customFetch);
export const indicatorsService = getIndicatorsService();
