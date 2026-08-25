<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { getSecurityService } from './securityService.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	let {
		open = $bindable(false),
		oncomplete
	}: {
		open?: boolean;
		oncomplete?: () => void;
	} = $props();

	const securityService = getSecurityService();

	let code = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (open) {
			code = '';
			error = null;
		}
	});

	async function handleSubmit(e?: SubmitEvent) {
		if (e) e.preventDefault();
		isSubmitting = true;
		error = null;

		try {
			await securityService.disableTotp(code.trim() ? { code: code.trim() } : {});
			open = false;
			if (oncomplete) oncomplete();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to disable two-factor authentication';
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
				<Dialog.Title>Disable two-factor authentication</Dialog.Title>
				<Dialog.Description>
					Disabling two-factor authentication makes your account less secure. Are you sure you want
					to turn off 2FA?
				</Dialog.Description>
			</Dialog.Header>

			{#if error}
				<Alert.Root variant="destructive">
					<Alert.Description>{error}</Alert.Description>
				</Alert.Root>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4 py-2">
				<div class="space-y-1.5">
					<Label for="disable-totp-code" class="text-xs text-muted-foreground">
						Authenticator code (optional)
					</Label>
					<Input
						id="disable-totp-code"
						type="text"
						inputmode="numeric"
						placeholder="6-digit code (optional)"
						bind:value={code}
						disabled={isSubmitting}
					/>
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
					<Button type="submit" variant="destructive" disabled={isSubmitting}>
						{#if isSubmitting}
							<Loader2 class="mr-2 h-4 w-4 animate-spin" />
							Disabling...
						{:else}
							Disable 2FA
						{/if}
					</Button>
				</Dialog.Footer>
			</form>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
