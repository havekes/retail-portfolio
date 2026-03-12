import { getBrokerService, type BrokerService } from './brokerService.svelte';
import type { BackendInstitution } from '@/types/broker/broker';

export class ConnectBrokerModalState {
	institutions = $state<BackendInstitution[]>([]);
	selectedInstitution = $state<BackendInstitution | null>(null);
	isLoginModalOpen = $state(false);
	errorMessage = $state<string | null>(null);

	private brokerService: BrokerService;

	constructor(private setOpen: (val: boolean) => void) {
		this.brokerService = getBrokerService();
	}

	reset = () => {
		this.selectedInstitution = null;
		this.errorMessage = null;
	};

	loadInstitutions = async () => {
		this.errorMessage = null;
		try {
			this.institutions = await this.brokerService.getAvailableInstitutions();
		} catch (e) {
			console.error('Failed to load institutions', e);
			this.errorMessage =
				e instanceof Error
					? e.message
					: 'Failed to load available institutions. Please try again later.';
		}
	};

	handleSelect = (id: string) => {
		const inst = this.institutions.find((i) => i.id === id);
		if (inst) {
			this.selectedInstitution = inst;
			this.setOpen(false);
			this.isLoginModalOpen = true;
		}
	};
}
