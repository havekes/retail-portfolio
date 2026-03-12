import { getBrokerService, type BrokerService } from './brokerService.svelte';
import type { BrokerUser } from '@/types/broker/broker';

export class BrokersListState {
	users = $state<BrokerUser[]>([]);
	isLoading = $state(false);
	errorMessage = $state<string | null>(null);
	isModalOpen = $state(false);

	private brokerService: BrokerService;

	constructor() {
		this.brokerService = getBrokerService();
	}

	loadUsers = async () => {
		this.isLoading = true;
		this.errorMessage = null;
		try {
			this.users = await this.brokerService.getBrokerUsers();
		} catch (error) {
			this.errorMessage = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			this.isLoading = false;
		}
	};

	openModal = () => {
		this.isModalOpen = true;
	};
}
