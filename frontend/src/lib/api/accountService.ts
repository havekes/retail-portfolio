import { ApiClient } from './apiClient';
import type { PaginatedResponse } from '../types/pagination';

export interface AccountHoldingRead {
	account_id: string;
	account_name: string;
	quantity: number;
	average_cost?: number;
	total_value: number;
	currency: string;
}

export class AccountService extends ApiClient {
	async getHoldings(securityId: string): Promise<PaginatedResponse<AccountHoldingRead>> {
		return await this.get<PaginatedResponse<AccountHoldingRead>>(`/accounts/holdings/${securityId}`);
	}
}

export const getAccountService = (customFetch?: typeof fetch) => new AccountService(customFetch);
export const accountService = getAccountService();
