import { BaseClient } from './baseClient';
import type { Account, AccountTotals } from '@/types/account';

export class AccountClient extends BaseClient {
	async getAccounts(): Promise<Account[]> {
		return this.get<Account[]>('/accounts/');
	}

	async renameAccount(id: string, name: string): Promise<Account> {
		return this.patch<Account, { name: string }>(`/accounts/${id}/rename`, { name });
	}

	async getAccountTotals(id: string): Promise<AccountTotals> {
		return this.get<AccountTotals>(`/accounts/${id}/totals`);
	}

	async deleteAccount(id: string): Promise<void> {
		return this.delete(`/accounts/${id}`);
	}

	async syncPositions(id: string): Promise<void> {
		await this.post<{ accepted: boolean }, undefined>(`/accounts/${id}/sync`, undefined);
	}
}

export const accountClient = new AccountClient();
