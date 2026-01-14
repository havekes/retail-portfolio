import { BaseService } from './baseService';
import type { Account, AccountTotals } from '@/types/account';

export class AccountService extends BaseService {
	async getAccounts(): Promise<Account[]> {
		return this.get<Account[]>('/accounts');
	}

	async renameAccount(id: string, name: string): Promise<void> {
		return this.patch(`/accounts/${id}/rename`, { name });
	}

	async getAccountTotals(id: string): Promise<AccountTotals> {
		return this.get<AccountTotals>(`/accounts/${id}/totals`);
	}
}

export const accountService = new AccountService();
