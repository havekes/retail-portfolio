import { getBrokerService, type BrokerService } from './brokerService.svelte';
import type { BrokerUser } from '@/types/broker/broker';

export class BrokersListState {
	users = $state<BrokerUser[]>([]);
	isLoading = $state(false);
	isModalOpen = $state(false);

	private brokerService: BrokerService;

	constructor(initialUsers: BrokerUser[] = []) {
		this.users = initialUsers;
		this.brokerService = getBrokerService();
	}

	loadUsers = async () => {
		this.isLoading = true;
		try {
			this.users = await this.brokerService.getBrokerUsers();
		} finally {
			this.isLoading = false;
		}
	};

	openModal = () => {
		this.isModalOpen = true;
	};
}
