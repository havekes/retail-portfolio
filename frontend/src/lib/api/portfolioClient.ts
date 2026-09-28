import { ApiClient } from './apiClient';
import type { Portfolio, PortfolioCreatePayload, PortfolioUpdatePayload } from '@/types/portfolio';

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

	async updatePortfolio(
		id: string,
		payload: PortfolioUpdatePayload,
		token?: string | null
	): Promise<Portfolio> {
		return this.patch<Portfolio, PortfolioUpdatePayload>(
			`/portfolios/${id}`,
			payload,
			undefined,
			token
		);
	}

	async deletePortfolio(id: string, token?: string | null): Promise<void> {
		return this.delete(`/portfolios/${id}`, undefined, token);
	}
}

export const getPortfolioClient = (customFetch?: typeof fetch) => new PortfolioClient(customFetch);
export const portfolioClient = getPortfolioClient();
