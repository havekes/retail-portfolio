import { ApiClient } from './apiClient';
import type { Account, AccountHoldings, AccountTotals } from '@/types/account';

export class AccountClient extends ApiClient {
	async getAccounts(token?: string | null): Promise<Account[]> {
		return this.get<Account[]>('/accounts/', {}, token);
	}

	async renameAccount(id: string, name: string): Promise<Account> {
		return this.patch<Account, { name: string }>(`/accounts/${id}/rename`, { name });
	}

	async getAccountTotals(id: string): Promise<AccountTotals> {
		return this.get<AccountTotals>(`/accounts/${id}/totals`);
	}

	async getAccountHoldings(id: string, token?: string | null): Promise<AccountHoldings> {
		return this.get<AccountHoldings>(`/accounts/${id}/holdings`, {}, token);
	}

	async deleteAccount(id: string): Promise<void> {
		return this.delete(`/accounts/${id}`);
	}

	async syncPositions(id: string): Promise<void> {
		await this.post<{ accepted: boolean }, undefined>(`/accounts/${id}/sync`, undefined);
	}
}

export const getAccountClient = (customFetch?: typeof fetch) => new AccountClient(customFetch);
export const accountClient = getAccountClient();
