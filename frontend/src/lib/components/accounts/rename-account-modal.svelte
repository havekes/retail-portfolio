<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	let {
		open = $bindable(false),
		currentName = '',
		onsave,
		onSave,
		oncancel,
		onCancel
	}: {
		open?: boolean;
		currentName?: string;
		onsave?: (name: string) => void | Promise<void>;
		onSave?: (name: string) => void | Promise<void>;
		oncancel?: () => void;
		onCancel?: () => void;
	} = $props();

	let name = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (open) {
			name = currentName;
			error = null;
		}
	});

	async function handleSubmit(e?: Event) {
		e?.preventDefault();
		const trimmed = name.trim();
		if (!trimmed) {
			error = 'Account name is required.';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			const saveFn = onsave ?? onSave;
			if (saveFn) {
				await saveFn(trimmed);
			}
			open = false;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to rename account';
		} finally {
			isSubmitting = false;
		}
	}

	function handleCancel() {
		const cancelFn = oncancel ?? onCancel;
		cancelFn?.();
		open = false;
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Rename account</Dialog.Title>
				<Dialog.Description>Enter a new name for this account.</Dialog.Description>
			</Dialog.Header>

			<form onsubmit={handleSubmit} class="space-y-4 py-2">
				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				<div class="space-y-2">
					<Label for="account-name">Account Name</Label>
					<Input
						id="account-name"
						bind:value={name}
						placeholder="Enter account name"
						disabled={isSubmitting}
						onkeydown={handleKeyDown}
					/>
				</div>

				<Dialog.Footer>
					<Button type="button" onclick={handleCancel} variant="outline" disabled={isSubmitting}>
						Cancel
					</Button>
					<Button type="submit" disabled={isSubmitting || !name.trim()}>
						{#if isSubmitting}
							<Loader2 class="mr-2 h-4 w-4 animate-spin" />
							Saving...
						{:else}
							Save
						{/if}
					</Button>
				</Dialog.Footer>
			</form>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
