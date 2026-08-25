<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import QRCode from 'qrcode';
	import { getSecurityService } from './securityService.svelte';
	import type { TotpSetupModalState } from './totp-setup-modal.svelte.js';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import Download from '@lucide/svelte/icons/download';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import ShieldCheck from '@lucide/svelte/icons/shield-check';

	let {
		open = $bindable(false),
		modalState,
		oncomplete
	}: {
		open?: boolean;
		modalState?: TotpSetupModalState;
		oncomplete?: () => void;
	} = $props();

	const securityService = getSecurityService();

	let step = $state<'setup' | 'backup_codes'>('setup');
	let secret = $state('');
	let qrDataUrl = $state('');
	let verificationCode = $state('');
	let recoveryCodes = $state<string[]>([]);
	let isInitializing = $state(false);
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);
	let copiedSecret = $state(false);
	let copiedCodes = $state(false);

	let isModalOpen = $derived(modalState ? modalState.isOpen : open);

	function setOpen(val: boolean) {
		if (modalState) {
			modalState.isOpen = val;
		} else {
			open = val;
		}
	}

	$effect(() => {
		if (isModalOpen) {
			resetAndInit();
		}
	});

	async function resetAndInit() {
		step = 'setup';
		secret = '';
		qrDataUrl = '';
		verificationCode = '';
		recoveryCodes = [];
		error = null;
		copiedSecret = false;
		copiedCodes = false;
		isInitializing = true;

		try {
			const res = await securityService.setupTotp();
			secret = res.secret;
			qrDataUrl = await QRCode.toDataURL(res.provisioning_uri, {
				width: 200,
				margin: 2,
				color: {
					dark: '#000000',
					light: '#ffffff'
				}
			});
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to initialize TOTP setup';
		} finally {
			isInitializing = false;
		}
	}

	async function handleCopySecret() {
		try {
			await navigator.clipboard.writeText(secret);
			copiedSecret = true;
			setTimeout(() => {
				copiedSecret = false;
			}, 2000);
		} catch {
			// Clipboard fallback handled silently
		}
	}

	async function handleCopyCodes() {
		try {
			await navigator.clipboard.writeText(recoveryCodes.join('\n'));
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
			recoveryCodes.join('\n') +
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

	async function handleSubmit(e?: SubmitEvent) {
		if (e) e.preventDefault();
		if (!verificationCode.trim() || verificationCode.trim().length !== 6) {
			error = 'Please enter a valid 6-digit verification code';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			const res = await securityService.activateTotp(verificationCode.trim());
			recoveryCodes = res.recovery_codes;
			step = 'backup_codes';
			if (oncomplete) oncomplete();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to verify code';
		} finally {
			isSubmitting = false;
		}
	}

	function handleClose() {
		setOpen(false);
	}
</script>

<Dialog.Root
	open={isModalOpen}
	onOpenChange={(val) => {
		if (!val) handleClose();
	}}
>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="sm:max-w-md">
			{#if step === 'setup'}
				<Dialog.Header>
					<Dialog.Title>Set up two-factor authentication</Dialog.Title>
					<Dialog.Description>
						Scan the QR code with your authenticator app (such as Google Authenticator, 1Password,
						or Authy), or enter the secret key manually.
					</Dialog.Description>
				</Dialog.Header>

				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				{#if isInitializing}
					<div class="flex flex-col items-center justify-center space-y-4 py-8">
						<Skeleton class="h-48 w-48 rounded-lg" />
						<Skeleton class="h-8 w-64" />
					</div>
				{:else}
					<div class="flex flex-col items-center space-y-4 py-2">
						{#if qrDataUrl}
							<div class="rounded-lg border bg-white p-2 shadow-xs">
								<img src={qrDataUrl} alt="TOTP QR Code" class="h-44 w-44" />
							</div>
						{/if}

						{#if secret}
							<div class="w-full space-y-1.5">
								<Label for="totp-secret" class="text-xs text-muted-foreground">Secret key</Label>
								<div class="flex items-center gap-2">
									<Input
										id="totp-secret"
										readonly
										value={secret}
										class="font-mono text-xs select-all"
									/>
									<Button
										type="button"
										variant="outline"
										size="icon"
										onclick={handleCopySecret}
										title="Copy secret key"
									>
										{#if copiedSecret}
											<Check class="h-4 w-4 text-green-500" />
										{:else}
											<Copy class="h-4 w-4" />
										{/if}
									</Button>
								</div>
							</div>
						{/if}

						<form onsubmit={handleSubmit} class="w-full space-y-4 pt-2">
							<div class="space-y-1.5">
								<Label for="verification-code">6-digit verification code</Label>
								<Input
									id="verification-code"
									type="text"
									inputmode="numeric"
									pattern="[0-9]*"
									maxlength={6}
									placeholder="123456"
									bind:value={verificationCode}
									class="text-center font-mono text-lg tracking-widest"
									disabled={isSubmitting}
								/>
							</div>

							<Dialog.Footer class="gap-2 sm:gap-0">
								<Button
									type="button"
									variant="outline"
									onclick={handleClose}
									disabled={isSubmitting}
								>
									Cancel
								</Button>
								<Button
									type="submit"
									disabled={isSubmitting || verificationCode.trim().length !== 6}
								>
									{#if isSubmitting}
										<Loader2 class="mr-2 h-4 w-4 animate-spin" />
										Verifying...
									{:else}
										Verify & activate
									{/if}
								</Button>
							</Dialog.Footer>
						</form>
					</div>
				{/if}
			{:else}
				<!-- Step 2: Backup Recovery Codes -->
				<Dialog.Header>
					<div class="flex items-center gap-2">
						<ShieldCheck class="h-5 w-5 text-green-500" />
						<Dialog.Title>Two-factor authentication enabled</Dialog.Title>
					</div>
					<Dialog.Description>
						Save these backup recovery codes in a secure password manager. If you lose access to
						your authenticator device, each recovery code can be used once to access your account.
					</Dialog.Description>
				</Dialog.Header>

				<div class="space-y-4 py-2">
					<div class="grid grid-cols-2 gap-2 rounded-lg border bg-muted/40 p-4 font-mono text-sm">
						{#each recoveryCodes as code (code)}
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
					<Button type="button" class="w-full sm:w-auto" onclick={handleClose}>
						I've saved my codes
					</Button>
				</Dialog.Footer>
			{/if}
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
