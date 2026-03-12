import { getBrokerService, type BrokerService } from './brokerService.svelte';
import { accountClient } from '$lib/api/accountClient';
import type { BrokerUser } from '@/types/broker/broker';
import type { Account } from '@/types/account';
import type { BrokerAccount } from '@/api/types/broker';

export interface SyncAccountsModalProps {
	open: boolean;
	brokerUser: BrokerUser;
	availableAccounts: BrokerAccount[];
	internalAccounts: Account[];
	onSave: () => void;
}

export class SyncAccountsModalState {
	checkedState = $state<Record<string, boolean>>({});
	isSaving = $state(false);
	confirmUnsyncOpen = $state(false);
	accountsToUnsync = $state<Account[]>([]);
	errorMessage = $state<string | null>(null);

	private brokerService: BrokerService;

	constructor(
		private getProps: () => SyncAccountsModalProps,
		private setOpen: (val: boolean) => void
	) {
		this.brokerService = getBrokerService();
	}

	initCheckedState = () => {
		const props = this.getProps();
		const newCheckedState: Record<string, boolean> = {};
		props.availableAccounts.forEach((acc: BrokerAccount) => {
			const isCurrentlySynced = props.internalAccounts.some(
				(iAcc: Account) => iAcc.external_id === acc.id
			);
			newCheckedState[acc.id] = isCurrentlySynced;
		});
		this.checkedState = newCheckedState;
	};

	handleToggle = (id: string) => {
		this.checkedState[id] = !this.checkedState[id];
	};

	handleSave = async () => {
		const props = this.getProps();
		const newlyCheckedExternalIds = Object.entries(this.checkedState)
			.filter(([, isChecked]) => isChecked)
			.map(([id]) => id);

		this.accountsToUnsync = props.internalAccounts.filter(
			(acc: Account) => this.checkedState[acc.external_id] === false
		);

		if (this.accountsToUnsync.length > 0) {
			this.confirmUnsyncOpen = true;
		} else {
			await this.performSync(newlyCheckedExternalIds);
		}
	};

	confirmSync = async () => {
		const newlyCheckedExternalIds = Object.entries(this.checkedState)
			.filter(([, isChecked]) => isChecked)
			.map(([id]) => id);
		await this.performSync(newlyCheckedExternalIds);
	};

	performSync = async (checkedExternalIds: string[]) => {
		this.isSaving = true;
		this.errorMessage = null;
		const props = this.getProps();
		try {
			if (checkedExternalIds.length > 0) {
				await this.brokerService.importBrokerAccounts(props.brokerUser.id, checkedExternalIds);
			}

			for (const acc of this.accountsToUnsync) {
				await accountClient.deleteAccount(acc.id);
			}

			this.setOpen(false);
			this.confirmUnsyncOpen = false;
			props.onSave();
		} catch (error) {
			console.error('Failed to sync accounts:', error);
			this.errorMessage =
				error instanceof Error ? error.message : 'Failed to sync accounts. Please try again.';
		} finally {
			this.isSaving = false;
		}
	};
}
