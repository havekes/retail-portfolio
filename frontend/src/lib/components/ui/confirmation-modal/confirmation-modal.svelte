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
		<!--
			Both the overlay and the content are raised above the standard z-50
			dialog layer. Confirmation dialogs can be opened from inside another
			dialog (e.g. deleting a note from the note view dialog); without a
			strictly higher z-index the confirm would tie with the note dialog
			and lose to portal/DOM order, rendering behind it and unclickable.
		-->
		<Dialog.Overlay class="z-[60]" />
		<Dialog.Content class="z-[60]" onkeydown={handleKeyDown}>
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
