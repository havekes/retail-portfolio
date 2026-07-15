import { ApiClient } from './apiClient';
import type { Portfolio, PortfolioCreatePayload } from '@/types/portfolio';

export class PortfolioClient extends ApiClient {
	async createPortfolio(payload: PortfolioCreatePayload): Promise<Portfolio> {
		return this.post<Portfolio, PortfolioCreatePayload>('/portfolios/', payload);
	}
}

export const getPortfolioClient = (customFetch?: typeof fetch) => new PortfolioClient(customFetch);
export const portfolioClient = getPortfolioClient();
