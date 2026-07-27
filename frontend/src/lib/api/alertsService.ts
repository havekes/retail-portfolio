import { ApiClient } from './apiClient';
import type { PaginatedResponse } from '../types/pagination';

export interface PriceAlert {
	id: number;
	security_id: string;
	user_id: string;
	target_price: number;
	condition: 'above' | 'below';
	triggered_at: string | null;
	created_at: string;
}

export interface PriceAlertCreateRequest {
	target_price: number;
	condition: 'above' | 'below';
}

export class AlertsService extends ApiClient {
	async getAlerts(securityId: string): Promise<PaginatedResponse<PriceAlert>> {
		return await this.get<PaginatedResponse<PriceAlert>>(`/market/securities/${securityId}/alerts`);
	}

	async createAlert(securityId: string, request: PriceAlertCreateRequest): Promise<PriceAlert> {
		return await this.post<PriceAlert, PriceAlertCreateRequest>(
			`/market/securities/${securityId}/alerts`,
			request
		);
	}

	async deleteAlert(securityId: string, alertId: number): Promise<void> {
		return await this.delete(`/market/securities/${securityId}/alerts/${alertId}`);
	}
}

export const alertsService = new AlertsService();
