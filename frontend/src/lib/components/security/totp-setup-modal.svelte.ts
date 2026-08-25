export class TotpSetupModalState {
	isOpen = $state(false);

	open = () => {
		this.isOpen = true;
	};

	close = () => {
		this.isOpen = false;
	};
}
