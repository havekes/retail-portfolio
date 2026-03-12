import { BaseService } from '../baseService';
import { userStore } from '@/stores/userStore';
import type { BrokerUser, BackendInstitution } from '@/types/broker/broker';

interface IntegrationUser {
	id: string;
	display_name: string;
	institution_id: number;
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
	async getInstitutions(): Promise<BackendInstitution[]> {
		return await this.get<BackendInstitution[]>('/integration/institutions');
	}

	async login(
		institutionId: string,
		payload: { username: string; password?: string; otp?: string }
	): Promise<void> {
		const token = userStore.getToken();
		const response = await fetch(`${this.baseUrl}/external/${institutionId}/login`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`
			},
			body: JSON.stringify(payload)
		});

		if (response.status === 400) {
			const errorData = await response.json();
			if (errorData.detail === 'OTP_REQUIRED') {
				throw new Error('OTP_REQUIRED');
			}
		}

		if (response.status === 401) {
			throw new Error('INVALID_CREDENTIALS');
		}

		if (!response.ok) {
			throw new Error('LOGIN_FAILED');
		}
	}
	async getBrokerUserAccounts(institutionId: number, externalUserId: string): Promise<any[]> {
		return await this.get<any[]>(`/external/${institutionId}/${externalUserId}/accounts`);
	}

	async importAccounts(
		institutionId: number,
		externalUserId: string,
		externalAccountIds: string[]
	): Promise<void> {
		return await this.post<void, any>(`/external/${institutionId}/accounts/import`, {
			external_user_id: externalUserId,
			external_account_ids: externalAccountIds
		});
	}

	async renameBrokerUser(institutionId: number, externalUserId: string, newName: string): Promise<void> {
		const token = userStore.getToken();
		const response = await fetch(`${this.baseUrl}/external/${institutionId}/users/${externalUserId}/display_name`, {
			method: 'PATCH',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`
			},
			body: JSON.stringify({ display_name: newName })
		});

		if (!response.ok) {
			throw new Error('RENAME_FAILED');
		}
	}
}

export const brokerService = new BrokerService();
