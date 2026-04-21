import { ApiClient } from './apiClient';

export interface MarketSearchResult {
	code: string;
	name: string;
	exchange: string;
	security_type: string;
}

export interface MarketPrice {
	id: number;
	security_id: string;
	date: string;
	open: number;
	high: number;
	low: number;
	close: number;
	adjusted_clost: number;
	volume: number;
	currency: string;
}

export interface MarketPriceHistory {
	security_id: string;
	from_date: string;
	to_date: string;
	prices: MarketPrice[];
}

export interface SecuritySchema {
	id: string;
	symbol: string;
	exchange: string;
	currency: string;
	name: string;
	isin: string | null;
	is_active: boolean;
	updated_at: string;
}

export interface SecurityCreateRequest {
	code: string;
	exchange: string;
	name: string;
	currency: string;
	isin?: string | null;
}

export interface SecurityCreateResponse {
	security_id: string;
	symbol: string;
	exchange: string;
	name: string;
	has_price_data: boolean;
}

export class MarketService extends ApiClient {
	async search(query: string): Promise<MarketSearchResult[]> {
		return await this.get<MarketSearchResult[]>(`/market/search?q=${query}`);
	}

	async getPrices(
		securityId: string,
		from_date: string,
		to_date: string
	): Promise<MarketPriceHistory> {
		return await this.get<MarketPriceHistory>(
			`/market/prices/${securityId}?from_date=${from_date}&to_date=${to_date}`
		);
	}

	async getLastClosePrice(securityId: string): Promise<MarketPrice> {
		return await this.get<MarketPrice>(`/market/prices/${securityId}/last-close`);
	}

	async getSecurity(securityId: string): Promise<SecuritySchema> {
		return await this.get<SecuritySchema>(`/market/securities/${securityId}`);
	}

	async createOrUpdateSecurity(request: SecurityCreateRequest): Promise<SecurityCreateResponse> {
		return await this.post<SecurityCreateResponse, SecurityCreateRequest>(
			'/market/security',
			request
		);
	}
}

export const marketService = new MarketService();
