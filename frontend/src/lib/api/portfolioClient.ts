import { ApiClient } from './apiClient';
import type { Portfolio, PortfolioCreatePayload } from '@/types/portfolio';

export class PortfolioClient extends ApiClient {
	async getPortfolios(token?: string | null): Promise<Portfolio[]> {
		return this.get<Portfolio[]>('/portfolios/', {}, token);
	}

	async createPortfolio(
		payload: PortfolioCreatePayload,
		token?: string | null
	): Promise<Portfolio> {
		return this.post<Portfolio, PortfolioCreatePayload>('/portfolios/', payload, undefined, token);
	}
}

export const getPortfolioClient = (customFetch?: typeof fetch) => new PortfolioClient(customFetch);
export const portfolioClient = getPortfolioClient();
