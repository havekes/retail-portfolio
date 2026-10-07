import { ApiClient } from './apiClient';
import type {
	Account,
	AccountHoldings,
	AccountTotals,
	CsvDiscoveredAccount
} from '@/types/account';

export interface SyncAccountCsvOptions {
	/** Net deposits to set; omit to leave the stored value unchanged. */
	netDeposits?: number | null;
}

export interface ImportAccountsCsvOptions {
	/** Per-account currency overrides keyed by account number. */
	currencies?: Record<string, string>;
	/** Net deposits keyed by account number. A `null` value clears it. */
	netDeposits?: Record<string, number | null>;
}

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

	async syncAccountCsv(
		accountId: string,
		file: File,
		optionsOrToken?: SyncAccountCsvOptions | string | null,
		token?: string | null
	): Promise<Account> {
		const options =
			optionsOrToken && typeof optionsOrToken === 'object' ? optionsOrToken : undefined;
		const actualToken = typeof optionsOrToken === 'string' ? optionsOrToken : token;

		const formData = new FormData();
		formData.append('file', file);
		if (options?.netDeposits !== undefined && options.netDeposits !== null) {
			formData.append('net_deposits', String(options.netDeposits));
		}
		return this.postFormData<Account>(
			`/accounts/${accountId}/csv-sync`,
			formData,
			undefined,
			actualToken
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
		optionsOrToken?: ImportAccountsCsvOptions | string | null,
		token?: string | null
	): Promise<Account[]> {
		const options =
			optionsOrToken && typeof optionsOrToken === 'object' ? optionsOrToken : undefined;
		const actualToken = typeof optionsOrToken === 'string' ? optionsOrToken : token;

		const formData = new FormData();
		formData.append('file', file);
		formData.append('institution_id', String(institutionId));
		for (const accountNumber of accountNumbers) {
			formData.append('account_numbers', accountNumber);
		}
		if (options?.currencies && Object.keys(options.currencies).length > 0) {
			formData.append('currencies', JSON.stringify(options.currencies));
		}
		if (options?.netDeposits && Object.keys(options.netDeposits).length > 0) {
			formData.append('net_deposits', JSON.stringify(options.netDeposits));
		}
		return this.postFormData<Account[]>('/accounts/csv/import', formData, undefined, actualToken);
	}
}

export const getAccountClient = (customFetch?: typeof fetch) => new AccountClient(customFetch);
export const accountClient = getAccountClient();
