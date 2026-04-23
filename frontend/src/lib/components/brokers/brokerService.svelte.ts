import { getBrokerClient, type BrokerClient } from '@/api/brokerClient';
import type { BrokerAccount, LoginCredentials } from '@/api/types/broker';
import type { BrokerUser, BackendInstitution } from '@/types/broker/broker';
import { Institution } from '@/types/account';
import { getContext, setContext } from 'svelte';

export class BrokerService {
	isLoading = $state(false);
	error = $state<string | null>(null);
	private client: BrokerClient;

	constructor(customFetch?: typeof fetch) {
		this.client = getBrokerClient(customFetch);
	}

	async getAvailableInstitutions(): Promise<BackendInstitution[]> {
		return this.client.getAvailableInstitutions();
	}

	async getBrokerUsers(token?: string | null): Promise<BrokerUser[]> {
		const users = await this.client.getBrokerUsers(token);
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
		return this.client.getBrokerUserAccounts(brokerUserId);
	}

	async login(institutionId: string, credentials: LoginCredentials): Promise<void> {
		return this.client.brokerLogin(institutionId, credentials);
	}

	async updateBrokerUserDisplayName(userId: string, name: string): Promise<void> {
		await this.client.updateBrokerUserDisplayName(userId, name);
	}

	async importBrokerAccounts(userId: string, externalIds: string[]): Promise<void> {
		await this.client.importBrokerAccounts(userId, externalIds);
	}
}

const BROKER_SERVICE_KEY = Symbol('broker-service');

export function setBrokerService() {
	const service = new BrokerService();
	setContext(BROKER_SERVICE_KEY, service);
	return service;
}

export function getBrokerService(customFetch?: typeof fetch) {
	if (customFetch) {
		return new BrokerService(customFetch);
	}
	return getContext<BrokerService>(BROKER_SERVICE_KEY);
}

