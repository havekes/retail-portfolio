import { ApiClient } from './apiClient';

export interface SecurityValuation {
	id: number;
	user_id: string;
	security_id: string;
	lower_bound: number;
	upper_bound: number;
	created_at: string;
	updated_at: string;
}

export type SecurityValuationRead = SecurityValuation;

export interface SecurityValuationWrite {
	lower_bound: number;
	upper_bound: number;
	notes?: string;
}

export class ValuationClient extends ApiClient {
	async getValuation(
		securityId: string,
		tokenOverride?: string | null
	): Promise<SecurityValuation | null> {
		try {
			return await this.get<SecurityValuation>(
				`/market/securities/${securityId}/valuation`,
				undefined,
				tokenOverride
			);
		} catch (err: unknown) {
			if (
				typeof err === 'object' &&
				err !== null &&
				'status' in err &&
				(err as { status: number }).status === 404
			) {
				return null;
			}
			if (err instanceof Error && err.message.includes('404')) {
				return null;
			}
			throw err;
		}
	}

	async saveValuation(
		securityId: string,
		lowerBound: number,
		upperBound: number,
		tokenOverride?: string | null
	): Promise<SecurityValuation> {
		return await this.put<SecurityValuation, { lower_bound: number; upper_bound: number }>(
			`/market/securities/${securityId}/valuation`,
			{ lower_bound: lowerBound, upper_bound: upperBound },
			undefined,
			tokenOverride
		);
	}

	async setValuation(
		securityId: string,
		data: SecurityValuationWrite,
		tokenOverride?: string | null
	): Promise<SecurityValuation> {
		return await this.saveValuation(securityId, data.lower_bound, data.upper_bound, tokenOverride);
	}

	async getBatchValuations(
		securityIds: string[],
		tokenOverride?: string | null
	): Promise<SecurityValuation[]> {
		if (!securityIds || securityIds.length === 0) return [];
		return await this.post<SecurityValuation[], { security_ids: string[] }>(
			'/market/securities/valuation/batch',
			{ security_ids: securityIds },
			undefined,
			tokenOverride
		);
	}
}

export const getValuationClient = (customFetch?: typeof fetch) => new ValuationClient(customFetch);
export const valuationClient = getValuationClient();
