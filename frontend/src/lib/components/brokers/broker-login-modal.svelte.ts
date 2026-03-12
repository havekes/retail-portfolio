import { getBrokerService, type BrokerService } from './brokerService.svelte';
import type { BackendInstitution } from '@/types/broker/broker';

export class BrokerLoginModalState {
	username = $state('');
	password = $state('');
	otp = $state('');
	isLoading = $state(false);
	error = $state<string | null>(null);
	requiresOtp = $state(false);

	private brokerService: BrokerService;

	constructor(
		private getInstitution: () => BackendInstitution | null,
		private onSuccess: () => void,
		private close: () => void
	) {
		this.brokerService = getBrokerService();
	}

	reset = () => {
		this.username = '';
		this.password = '';
		this.otp = '';
		this.requiresOtp = false;
		this.error = null;
	};

	handleSubmit = async (e: Event) => {
		e.preventDefault();
		const institution = this.getInstitution();
		if (!institution || !this.username) return;

		this.isLoading = true;
		this.error = null;

		try {
			await this.brokerService.login(institution.id, {
				username: this.username,
				password: this.password ? this.password : undefined,
				otp: this.requiresOtp ? this.otp : undefined
			});
			this.close();
			this.onSuccess();
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : '';
			if (msg === 'OTP_REQUIRED') {
				this.requiresOtp = true;
			} else if (msg === 'INVALID_CREDENTIALS') {
				this.error = 'Invalid username or password';
			} else {
				this.error = 'Login failed. Please try again.';
			}
		} finally {
			this.isLoading = false;
		}
	};
}
