import { ApiClient } from './apiClient';
import type { PaginatedResponse } from '../types/pagination';

export interface MarketSearchResult {
	code: string;
	name: string;
	exchange: string;
	security_type: string;
}

export interface MarketPrice {
	id?: number;
	security_id?: string;
	date?: string;
	timestamp?: string;
	open: number;
	high: number;
	low: number;
	close: number;
	adjusted_close?: number;
	adjusted_clost?: number;
	volume: number;
	currency?: string;
}

export interface MarketPriceHistory extends PaginatedResponse<MarketPrice> {
	security_id: string;
	from_date?: string;
	to_date?: string;
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

export interface WatchlistRead {
	id: string;
	user_id: string;
	name: string;
}

export class MarketService extends ApiClient {
	async search(query: string): Promise<MarketSearchResult[]> {
		return await this.get<MarketSearchResult[]>(`/market/search?q=${query}`);
	}

	async getPrices(
		securityId: string,
		from_date?: string,
		to_date?: string,
		interval: string = "1d",
		token?: string | null
	): Promise<MarketPriceHistory> {
		let url = `/market/prices/${securityId}?interval=${interval}`;
		if (from_date) {
			url += `&from_date=${from_date}`;
		}
		if (to_date) {
			url += `&to_date=${to_date}`;
		}
		return await this.get<MarketPriceHistory>(url, {}, token);
	}

	async getLastClosePrice(securityId: string, token?: string | null): Promise<MarketPrice> {
		return await this.get<MarketPrice>(`/market/prices/${securityId}/last-close`, {}, token);
	}

	async getSecurity(securityId: string, token?: string | null): Promise<SecuritySchema> {
		return await this.get<SecuritySchema>(`/market/securities/${securityId}`, {}, token);
	}

	async createOrUpdateSecurity(request: SecurityCreateRequest): Promise<SecurityCreateResponse> {
		return await this.post<SecurityCreateResponse, SecurityCreateRequest>(
			'/market/security',
			request
		);
	}

	async getWatchlists(token?: string | null): Promise<WatchlistRead[]> {
		return await this.get<WatchlistRead[]>('/market/watchlists', {}, token);
	}

	async getWatchlistSecurities(
		watchlistId: string,
		token?: string | null
	): Promise<PaginatedResponse<SecuritySchema>> {
		return await this.get<PaginatedResponse<SecuritySchema>>(
			`/market/watchlists/${watchlistId}/securities`,
			{},
			token
		);
	}

	async addToWatchlist(securityId: string, token?: string | null): Promise<WatchlistRead> {
		return await this.post<WatchlistRead, Record<string, never>>(
			`/market/watchlists/securities/${securityId}`,
			{},
			{},
			token
		);
	}

	async removeFromWatchlist(securityId: string, token?: string | null): Promise<WatchlistRead> {
		return await this.delete<WatchlistRead>(
			`/market/watchlists/securities/${securityId}`,
			{},
			token
		);
	}
}

export const getMarketService = (customFetch?: typeof fetch) => new MarketService(customFetch);
export const marketService = getMarketService();
