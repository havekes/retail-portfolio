import { ApiClient } from './apiClient';

export interface AIAnalysisResponse {
	content: string;
	generated_at: string;
}

export interface AIAnalysisRequest {
	portfolio_context?: string;
}

export class AIService extends ApiClient {
	async analyzeFundamentals(securityId: string): Promise<AIAnalysisResponse> {
		return this.post(`/market/securities/${securityId}/ai/fundamentals`, {});
	}

	async summarizeNotes(securityId: string): Promise<AIAnalysisResponse> {
		return this.post(`/market/securities/${securityId}/ai/summarize-notes`, {});
	}

	async analyzePortfolioFit(
		securityId: string,
		request: AIAnalysisRequest
	): Promise<AIAnalysisResponse> {
		return this.post(`/market/securities/${securityId}/ai/portfolio-debate`, request);
	}
}

export const aiService = new AIService();
