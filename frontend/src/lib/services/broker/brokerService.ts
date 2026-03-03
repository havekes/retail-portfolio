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
}

export const brokerService = new BrokerService();
