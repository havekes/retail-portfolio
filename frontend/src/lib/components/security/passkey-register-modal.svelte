<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { getSecurityService } from './securityService.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import Fingerprint from '@lucide/svelte/icons/fingerprint';

	let {
		open = $bindable(false),
		oncomplete
	}: {
		open?: boolean;
		oncomplete?: () => void;
	} = $props();

	const securityService = getSecurityService();

	let passkeyName = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (open) {
			passkeyName = 'Passkey';
			error = null;
		}
	});

	async function handleSubmit(e?: SubmitEvent) {
		if (e) e.preventDefault();
		if (!passkeyName.trim()) {
			error = 'Please enter a name for your passkey';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			await securityService.registerPasskey(passkeyName.trim());
			open = false;
			if (oncomplete) oncomplete();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to register passkey';
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
					<Fingerprint class="h-5 w-5 text-primary" />
					<Dialog.Title>Add new passkey</Dialog.Title>
				</div>
				<Dialog.Description>
					Passkeys allow you to sign in securely using your fingerprint, face recognition, or a
					security key.
				</Dialog.Description>
			</Dialog.Header>

			{#if error}
				<Alert.Root variant="destructive">
					<Alert.Description>{error}</Alert.Description>
				</Alert.Root>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4 py-2">
				<div class="space-y-1.5">
					<Label for="passkey-name">Passkey name</Label>
					<Input
						id="passkey-name"
						type="text"
						placeholder="e.g. MacBook Touch ID, iPhone, YubiKey"
						bind:value={passkeyName}
						disabled={isSubmitting}
					/>
				</div>

				{#if isSubmitting}
					<div
						class="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground"
					>
						<div class="flex items-center gap-2">
							<Loader2 class="h-4 w-4 animate-spin text-primary" />
							<span>Follow the instructions on your device to create your passkey...</span>
						</div>
					</div>
				{/if}

				<Dialog.Footer class="gap-2 sm:gap-0">
					<Button
						type="button"
						variant="outline"
						onclick={() => (open = false)}
						disabled={isSubmitting}
					>
						Cancel
					</Button>
					<Button type="submit" disabled={isSubmitting || !passkeyName.trim()}>
						{#if isSubmitting}
							<Loader2 class="mr-2 h-4 w-4 animate-spin" />
							Registering...
						{:else}
							Continue
						{/if}
					</Button>
				</Dialog.Footer>
			</form>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
