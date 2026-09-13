import { ApiClient } from './apiClient';
import type {
	Account,
	AccountHoldings,
	AccountTotals,
	CsvDiscoveredAccount
} from '@/types/account';

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

	async inspectCsv(
		institutionId: string | number,
		file: File,
		token?: string | null
	): Promise<CsvDiscoveredAccount[]> {
		const formData = new FormData();
		formData.append('file', file);
		formData.append('institution_id', String(institutionId));
		return this.postFormData<CsvDiscoveredAccount[]>(
			'/accounts/csv/inspect',
			formData,
			undefined,
			token
		);
	}

	async importAccountsCsv(
		institutionId: string | number,
		file: File,
		accountNumbers: string[],
		token?: string | null
	): Promise<Account[]> {
		const formData = new FormData();
		formData.append('file', file);
		formData.append('institution_id', String(institutionId));
		for (const accountNumber of accountNumbers) {
			formData.append('account_numbers', accountNumber);
		}
		return this.postFormData<Account[]>('/accounts/csv/import', formData, undefined, token);
	}
}

export const getAccountClient = (customFetch?: typeof fetch) => new AccountClient(customFetch);
export const accountClient = getAccountClient();
