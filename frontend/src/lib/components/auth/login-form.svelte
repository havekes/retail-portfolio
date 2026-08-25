<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { FieldGroup, Field, FieldDescription } from '$lib/components/ui/field/index.js';
	import { enhance, deserialize } from '$app/forms';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { authService } from '$lib/api/authService';
	import { startAuthentication, browserSupportsWebAuthn } from '@simplewebauthn/browser';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import Fingerprint from '@lucide/svelte/icons/fingerprint';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import Shield from '@lucide/svelte/icons/shield';

	let { form } = $props();
	const id = $props.id();

	let customEmail = $state<string | null>(null);
	const email = $derived(customEmail ?? form?.email ?? '');
	let password = $state('');
	let code = $state('');
	let isRecoveryCode = $state(false);
	let isLoading = $state(false);
	let isPasskeyLoading = $state(false);
	let localError = $state<string | null>(null);
	let is2faCancelled = $state(false);

	const show2fa = $derived(Boolean(form?.requires2fa && !is2faCancelled));
	const mfaToken = $derived(form?.mfaToken ?? '');
	const errorMessage = $derived(localError ?? form?.message ?? null);

	async function handlePasskeyLogin() {
		localError = null;

		if (!browserSupportsWebAuthn()) {
			localError = 'WebAuthn is not supported on this device or browser';
			return;
		}

		isPasskeyLoading = true;

		try {
			const targetEmail = email.trim();
			const options = await authService.getPasskeyAuthOptions(
				targetEmail ? { email: targetEmail } : undefined
			);

			let credential;
			try {
				credential = await startAuthentication({ optionsJSON: options });
			} catch (authErr: unknown) {
				const e = authErr as { name?: string; message?: string };
				if (e?.name === 'NotAllowedError') {
					localError = 'Passkey authentication was cancelled or timed out';
					return;
				}
				localError = e?.message || 'Failed to complete passkey authentication';
				return;
			}

			const formData = new FormData();
			formData.append('credential', JSON.stringify(credential));
			if (targetEmail) {
				formData.append('email', targetEmail);
			}

			const res = await fetch('?/passkeyLogin', {
				method: 'POST',
				body: formData
			});

			const result = deserialize(await res.text());

			if (result.type === 'redirect') {
				await goto(resolve(result.location as '/'));
			} else if (result.type === 'failure') {
				const data = result.data as { message?: string } | undefined;
				localError = data?.message || 'Passkey authentication failed';
			} else if (result.type === 'error') {
				localError = result.error?.message || 'Passkey authentication failed';
			} else if (result.type === 'success') {
				await goto(resolve('/'));
			}
		} catch (err: unknown) {
			const message = err instanceof Error ? err.message : 'Passkey authentication failed';
			localError = message;
		} finally {
			isPasskeyLoading = false;
		}
	}

	function handleBackToLogin() {
		is2faCancelled = true;
		code = '';
		isRecoveryCode = false;
		localError = null;
		customEmail = null;
	}

	function toggleRecoveryMode() {
		isRecoveryCode = !isRecoveryCode;
		code = '';
		localError = null;
	}
</script>

{#if show2fa}
	<Card.Root class="mx-auto w-full max-w-sm">
		<Card.Header>
			<div class="flex items-center gap-2">
				<Shield class="h-5 w-5 text-primary" />
				<Card.Title class="text-2xl">Two-Factor Authentication</Card.Title>
			</div>
			<Card.Description>
				{isRecoveryCode
					? 'Enter an 8-character recovery code.'
					: 'Enter the 6-digit verification code from your authenticator app.'}
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<form
				method="POST"
				action="?/verify2fa"
				use:enhance={() => {
					isLoading = true;
					localError = null;
					return async ({ update }) => {
						isLoading = false;
						await update();
					};
				}}
			>
				<input type="hidden" name="mfaToken" value={mfaToken} />
				<input type="hidden" name="email" value={email} />

				<FieldGroup>
					<Field>
						{#if isRecoveryCode}
							<Input
								id="code-{id}"
								name="code"
								type="text"
								placeholder="Recovery Code (e.g. 1a2b3c4d)"
								maxlength={8}
								autocomplete="off"
								required
								bind:value={code}
								disabled={isLoading}
							/>
						{:else}
							<Input
								id="code-{id}"
								name="code"
								type="text"
								inputmode="numeric"
								maxlength={6}
								pattern="[0-9]{6}"
								autocomplete="one-time-code"
								placeholder="6-digit code"
								required
								bind:value={code}
								disabled={isLoading}
							/>
						{/if}
					</Field>

					{#if errorMessage}
						<p class="text-sm text-red-500">{errorMessage}</p>
					{/if}

					<Field>
						<Button type="submit" class="w-full" disabled={isLoading || !code.trim()}>
							{isLoading ? 'Verifying...' : 'Verify'}
						</Button>
					</Field>

					<div class="flex flex-col items-center gap-2 pt-2">
						<Button
							type="button"
							variant="link"
							class="h-auto p-0 text-xs text-muted-foreground hover:text-foreground"
							onclick={toggleRecoveryMode}
						>
							{isRecoveryCode ? 'Use authenticator app instead' : 'Use a recovery code instead'}
						</Button>

						<Button
							type="button"
							variant="ghost"
							class="flex w-full items-center justify-center gap-2 text-xs"
							onclick={handleBackToLogin}
						>
							<ArrowLeft class="h-3.5 w-3.5" />
							<span>Back to login</span>
						</Button>
					</div>
				</FieldGroup>
			</form>
		</Card.Content>
	</Card.Root>
{:else}
	<Card.Root class="mx-auto w-full max-w-sm">
		<Card.Header>
			<Card.Title class="text-2xl">Login</Card.Title>
			<Card.Description>Enter your email below to login to your account</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<Button
					type="button"
					variant="outline"
					class="flex w-full items-center justify-center gap-2"
					onclick={handlePasskeyLogin}
					disabled={isLoading || isPasskeyLoading}
				>
					{#if isPasskeyLoading}
						<Loader2 class="h-4 w-4 animate-spin" />
						<span>Authenticating passkey...</span>
					{:else}
						<Fingerprint class="h-4 w-4" />
						<span>Sign in with a Passkey</span>
					{/if}
				</Button>

				<div
					class="relative flex items-center justify-center text-xs text-muted-foreground uppercase"
				>
					<div class="w-full border-t border-border"></div>
					<span class="bg-card px-2 text-muted-foreground">or</span>
					<div class="w-full border-t border-border"></div>
				</div>

				<form
					method="POST"
					action="?/login"
					use:enhance={() => {
						isLoading = true;
						localError = null;
						return async ({ update }) => {
							isLoading = false;
							await update();
						};
					}}
				>
					<FieldGroup>
						<Field>
							<Input
								id="email-{id}"
								name="email"
								type="email"
								placeholder="Email"
								required
								value={email}
								oninput={(e) => {
									customEmail = (e.currentTarget as HTMLInputElement).value;
								}}
								disabled={isLoading || isPasskeyLoading}
							/>
						</Field>
						<Field>
							<Input
								id="password-{id}"
								name="password"
								type="password"
								placeholder="Password"
								required
								bind:value={password}
								disabled={isLoading || isPasskeyLoading}
							/>
						</Field>
						{#if errorMessage}
							<p class="text-sm text-red-500">{errorMessage}</p>
						{/if}
						<Field>
							<Button type="submit" class="w-full" disabled={isLoading || isPasskeyLoading}>
								{isLoading ? 'Logging in...' : 'Login'}
							</Button>
							<FieldDescription class="text-center">
								Don't have an account? <a href={resolve('/auth/signup')}>Sign up for free</a>
							</FieldDescription>
						</Field>
					</FieldGroup>
				</form>
			</div>
		</Card.Content>
	</Card.Root>
{/if}
