import { ApiClient } from './apiClient';

export interface AccountHoldingRead {
	account_id: string;
	account_name: string;
	quantity: number;
	average_cost?: number;
	total_value: number;
	currency: string;
}

export class AccountService extends ApiClient {
	async getHoldings(securityId: string): Promise<AccountHoldingRead[]> {
		return await this.get<AccountHoldingRead[]>(`/accounts/holdings/${securityId}`);
	}
}

export const getAccountService = (customFetch?: typeof fetch) => new AccountService(customFetch);
export const accountService = getAccountService();
