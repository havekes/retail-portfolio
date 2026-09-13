import { ApiClient } from './apiClient';
import type { Account, AccountHoldings, AccountTotals } from '@/types/account';

export class AccountClient extends ApiClient {
	async getAccounts(token?: string | null): Promise<Account[]> {
		return this.get<Account[]>('/accounts/', {}, token);
	}

	async renameAccount(id: string, name: string, token?: string | null): Promise<Account> {
		return this.patch<Account, { name: string }>(
			`/accounts/${id}/rename`,
			{ name },
			undefined,
			token
		);
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

	async getSyncStatus(): Promise<{ account_ids: string[] }> {
		return this.get<{ account_ids: string[] }>('/accounts/sync-status');
	}

	async syncAccountCsv(accountId: string, file: File, token?: string | null): Promise<Account> {
		const formData = new FormData();
		formData.append('file', file);
		return this.postFormData<Account>(
			`/accounts/${accountId}/csv-sync`,
			formData,
			undefined,
			token
		);
	}
}

export const getAccountClient = (customFetch?: typeof fetch) => new AccountClient(customFetch);
export const accountClient = getAccountClient();
