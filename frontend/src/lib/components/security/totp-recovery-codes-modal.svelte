<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { getSecurityService } from './securityService.svelte';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import Download from '@lucide/svelte/icons/download';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import AlertTriangle from '@lucide/svelte/icons/triangle-alert';

	let {
		open = $bindable(false),
		oncomplete
	}: {
		open?: boolean;
		oncomplete?: () => void;
	} = $props();

	const securityService = getSecurityService();

	let codes = $state<string[]>([]);
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);
	let copiedCodes = $state(false);

	$effect(() => {
		if (open) {
			codes = [];
			error = null;
			copiedCodes = false;
		}
	});

	async function handleRegenerate() {
		isSubmitting = true;
		error = null;

		try {
			const res = await securityService.regenerateRecoveryCodes();
			codes = res;
			if (oncomplete) oncomplete();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to regenerate recovery codes';
		} finally {
			isSubmitting = false;
		}
	}

	async function handleCopyCodes() {
		try {
			await navigator.clipboard.writeText(codes.join('\n'));
			copiedCodes = true;
			setTimeout(() => {
				copiedCodes = false;
			}, 2000);
		} catch {
			// Clipboard fallback handled silently
		}
	}

	function handleDownloadCodes() {
		const text =
			`Retail Portfolio 2FA Backup Recovery Codes\nGenerated: ${new Date().toISOString()}\n\n` +
			codes.join('\n') +
			'\n\nKeep these codes safe. Each code can be used once.';
		const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = 'retail-portfolio-recovery-codes.txt';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="sm:max-w-md">
			{#if codes.length === 0}
				<Dialog.Header>
					<div class="flex items-center gap-2">
						<RefreshCw class="h-5 w-5" />
						<Dialog.Title>Regenerate recovery codes</Dialog.Title>
					</div>
					<Dialog.Description>
						Regenerating your recovery codes will invalidate all previously generated codes. Make
						sure to save the new codes.
					</Dialog.Description>
				</Dialog.Header>

				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				<div
					class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300"
				>
					<div class="flex gap-2">
						<AlertTriangle class="h-4 w-4 shrink-0" />
						<span>Any existing unused recovery codes will no longer work after regenerating.</span>
					</div>
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
					<Button onclick={handleRegenerate} disabled={isSubmitting}>
						{#if isSubmitting}
							<Loader2 class="mr-2 h-4 w-4 animate-spin" />
							Generating...
						{:else}
							Generate new codes
						{/if}
					</Button>
				</Dialog.Footer>
			{:else}
				<Dialog.Header>
					<Dialog.Title>New recovery codes</Dialog.Title>
					<Dialog.Description>
						Save these backup recovery codes in a secure password manager. Each code can only be
						used once.
					</Dialog.Description>
				</Dialog.Header>

				<div class="space-y-4 py-2">
					<div class="grid grid-cols-2 gap-2 rounded-lg border bg-muted/40 p-4 font-mono text-sm">
						{#each codes as code (code)}
							<div class="rounded border bg-background px-2.5 py-1.5 text-center select-all">
								{code}
							</div>
						{/each}
					</div>

					<div class="flex items-center gap-2">
						<Button
							type="button"
							variant="outline"
							size="sm"
							class="flex-1"
							onclick={handleCopyCodes}
						>
							{#if copiedCodes}
								<Check class="mr-1.5 h-4 w-4 text-green-500" />
								Copied!
							{:else}
								<Copy class="mr-1.5 h-4 w-4" />
								Copy all codes
							{/if}
						</Button>
						<Button
							type="button"
							variant="outline"
							size="sm"
							class="flex-1"
							onclick={handleDownloadCodes}
						>
							<Download class="mr-1.5 h-4 w-4" />
							Download .txt
						</Button>
					</div>
				</div>

				<Dialog.Footer>
					<Button type="button" class="w-full sm:w-auto" onclick={() => (open = false)}>
						I've saved my codes
					</Button>
				</Dialog.Footer>
			{/if}
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
