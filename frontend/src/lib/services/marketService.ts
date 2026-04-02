import { BaseService } from './baseService';

export interface MarketSearchResult {
	code: string;
	name: string;
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

export class MarketService extends BaseService {
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
}

export const marketService = new MarketService();
