<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import type { PasskeyResponse } from '$lib/api/types/security';
	import { getSecurityService } from './securityService.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import Pencil from '@lucide/svelte/icons/pencil';

	let {
		open = $bindable(false),
		passkey,
		oncomplete
	}: {
		open?: boolean;
		passkey?: PasskeyResponse | null;
		oncomplete?: () => void;
	} = $props();

	const securityService = getSecurityService();

	let name = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (open && passkey) {
			name = passkey.name;
			error = null;
		}
	});

	async function handleSubmit(e?: SubmitEvent) {
		if (e) e.preventDefault();
		if (!name.trim()) {
			error = 'Passkey name cannot be empty';
			return;
		}
		if (!passkey) return;

		isSubmitting = true;
		error = null;

		try {
			await securityService.renamePasskey(passkey.id, name.trim());
			open = false;
			if (oncomplete) oncomplete();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to rename passkey';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="sm:max-w-md">
			<Dialog.Header>
				<div class="flex items-center gap-2">
					<Pencil class="h-5 w-5 text-primary" />
					<Dialog.Title>Rename passkey</Dialog.Title>
				</div>
				<Dialog.Description>
					Choose a descriptive name to help identify this passkey.
				</Dialog.Description>
			</Dialog.Header>

			{#if error}
				<Alert.Root variant="destructive">
					<Alert.Description>{error}</Alert.Description>
				</Alert.Root>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4 py-2">
				<div class="space-y-1.5">
					<Label for="rename-passkey-name">Passkey name</Label>
					<Input id="rename-passkey-name" type="text" bind:value={name} disabled={isSubmitting} />
				</div>

				<Dialog.Footer class="gap-2 sm:gap-0">
					<Button
						type="button"
						variant="outline"
						onclick={() => (open = false)}
						disabled={isSubmitting}
					>
						Cancel
					</Button>
					<Button type="submit" disabled={isSubmitting || !name.trim()}>
						{#if isSubmitting}
							<Loader2 class="mr-2 h-4 w-4 animate-spin" />
							Saving...
						{:else}
							Save changes
						{/if}
					</Button>
				</Dialog.Footer>
			</form>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
