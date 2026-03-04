import { BaseService } from '../baseService';
import type { BrokerUser } from '@/types/broker/broker';

interface BackendInstitution {
	id: number;
}

interface IntegrationUser {
	id: string;
	display_name: string;
	institution_id: number;
}

export interface BrokerAccountModel {
	id: string;
	type: number;
	institution: number;
	currency: string;
	display_name: string;
	value: number;
	created_at: string;
}

export class BrokerService extends BaseService {
	async getBrokerUsers(): Promise<BrokerUser[]> {
		const institutions = await this.get<BackendInstitution[]>('/integration/institutions');

		const brokerUsersPromises = institutions.map(async (inst) => {
			const users = await this.get<IntegrationUser[]>(`/external/${inst.id}/users`);
			return users.map(
				(u) =>
					({
						id: u.id,
						name: u.display_name || 'Account',
						institution_id: u.institution_id,
						accounts_synced: 0,
						accounts_total: 0
					}) as BrokerUser
			);
		});

		const usersArrays = await Promise.all(brokerUsersPromises);
		return usersArrays.flat();
	}

	async getAccounts(institutionId: number, externalUserId: string): Promise<BrokerAccountModel[]> {
		return this.get<BrokerAccountModel[]>(`/external/${institutionId}/${externalUserId}/accounts`);
	}

	async importAccounts(
		institutionId: number,
		externalUserId: string,
		externalAccountIds: string[]
	): Promise<{ imported_count: number }> {
		return this.post<
			{ imported_count: number },
			{ external_user_id: string; external_account_ids: string[] }
		>(`/external/${institutionId}/accounts/import`, {
			external_user_id: externalUserId,
			external_account_ids: externalAccountIds
		});
	}

	async login(
		institutionId: number,
		request: { username: string; password?: string; otp?: string }
	): Promise<{ login_succes: boolean }> {
		return this.post<
			{ login_succes: boolean },
			{ username: string; password?: string; otp?: string }
		>(`/external/${institutionId}/login`, request);
	}
}

export const brokerService = new BrokerService();
