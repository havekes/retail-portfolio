import { BaseClient } from './baseClient';
import type {
	Institution,
	BrokerUser,
	BrokerAccount,
	LoginCredentials,
	ImportBrokerAccountsResponse
} from './types/broker';

export class BrokerClient extends BaseClient {
	async getAvailableInstitutions(): Promise<Institution[]> {
		return this.get<Institution[]>('/integration/institutions');
	}

	async getBrokerUsers(): Promise<BrokerUser[]> {
		return this.get<BrokerUser[]>('/external/users');
	}

	async getBrokerUserAccounts(brokerUserId: string): Promise<BrokerAccount[]> {
		return this.get<BrokerAccount[]>(`/external/users/${brokerUserId}/accounts`);
	}

	async brokerLogin(institutionId: string, credentials: LoginCredentials): Promise<void> {
		return this.post<void, LoginCredentials>(`/external/${institutionId}/login`, credentials);
	}

	async updateBrokerUserDisplayName(
		externalUserId: string,
		displayName: string
	): Promise<BrokerUser> {
		return this.patch<BrokerUser, { display_name: string }>(
			`/external/users/${externalUserId}/display_name`,
			{ display_name: displayName }
		);
	}

	async importBrokerAccounts(
		externalUserId: string,
		externalAccountIds: string[]
	): Promise<ImportBrokerAccountsResponse> {
		return this.post<
			ImportBrokerAccountsResponse,
			{ external_user_id: string; external_account_ids: string[] }
		>('/external/accounts/import', {
			external_user_id: externalUserId,
			external_account_ids: externalAccountIds
		});
	}
}

export const brokerClient = new BrokerClient();
