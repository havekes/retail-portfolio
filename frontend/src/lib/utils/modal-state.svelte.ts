export class ModalState<T = void> {
	isOpen = $state(false);
	data = $state<T | null>(null);

	public open = (data?: T) => {
		this.isOpen = true;
		if (data !== undefined) {
			this.data = data;
		}
	};

	public close = () => {
		this.isOpen = false;
		this.reset();
	};

	public reset = () => {
		this.data = null;
	};
}
