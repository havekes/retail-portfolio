<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import Button from '@/components/ui/button/button.svelte';

	let { open = $bindable(false), title = 'Confirm Action', description = 'Are you sure?', onconfirm, oncancel } = $props<{
		open?: boolean;
		title?: string;
		description?: string;
		onconfirm: () => void;
		oncancel?: () => void;
	}>();

	const handleConfirm = () => {
		onconfirm();
		open = false;
	};

	const handleCancel = () => {
		if (oncancel) oncancel();
		open = false;
	};

	const handleKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleConfirm();
		}
	};
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content onkeydown={handleKeyDown}>
			<Dialog.Header>
				<Dialog.Title>{title}</Dialog.Title>
				<Dialog.Description class="py-2">
					{description}
				</Dialog.Description>
			</Dialog.Header>

			<Dialog.Footer>
				<Button onclick={handleCancel} variant="outline">Cancel</Button>
				<Button onclick={handleConfirm} variant="destructive">Confirm</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
