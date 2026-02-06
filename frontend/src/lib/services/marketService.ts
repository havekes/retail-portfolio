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

export interface MarketPriceRequest {
	security_id: string;
	from_date: string;
	to_date: string;
}

export class MarketService extends BaseService {
	async search(query: string): Promise<MarketSearchResult[]> {
		return await this.get<MarketSearchResult[]>(`/market/search?query=${query}`);
	}

	async getPrices(request: MarketPriceRequest): Promise<MarketPrice> {
		return await this.post<MarketPrice, MarketPriceRequest>('/market/prices', request);
	}
}

export const marketService = new MarketService();
