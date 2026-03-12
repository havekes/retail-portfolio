import { brokerClient } from '@/api/brokerClient';
import type { BrokerAccount, LoginCredentials } from '@/api/types/broker';
import type { BrokerUser, BackendInstitution } from '@/types/broker/broker';
import { Institution } from '@/types/account';
import { getContext, setContext } from 'svelte';

export class BrokerService {
	isLoading = $state(false);
	error = $state<string | null>(null);

	async getAvailableInstitutions(): Promise<BackendInstitution[]> {
		return brokerClient.getAvailableInstitutions();
	}

	async getBrokerUsers(): Promise<BrokerUser[]> {
		const users = await brokerClient.getBrokerUsers();
		return users.map((u) => {
			const fallbackName =
				typeof u.institution_id === 'number'
					? `${Institution[u.institution_id]} Connection`
					: 'Connection';

			return {
				id: u.id,
				displayName: u.display_name || fallbackName,
				institution_id: u.institution_id
			};
		});
	}

	async getBrokerUserAccounts(brokerUserId: string): Promise<BrokerAccount[]> {
		return brokerClient.getBrokerUserAccounts(brokerUserId);
	}

	async login(institutionId: string, credentials: LoginCredentials): Promise<void> {
		return brokerClient.brokerLogin(institutionId, credentials);
	}

	async updateBrokerUserDisplayName(userId: string, name: string): Promise<void> {
		await brokerClient.updateBrokerUserDisplayName(userId, name);
	}

	async importBrokerAccounts(userId: string, externalIds: string[]): Promise<void> {
		await brokerClient.importBrokerAccounts(userId, externalIds);
	}
}

const BROKER_SERVICE_KEY = Symbol('broker-service');

export function setBrokerService() {
	const service = new BrokerService();
	setContext(BROKER_SERVICE_KEY, service);
	return service;
}

export function getBrokerService() {
	return getContext<BrokerService>(BROKER_SERVICE_KEY);
}
