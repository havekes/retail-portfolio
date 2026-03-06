<script lang="ts">
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogDescription
	} from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Button } from '$lib/components/ui/button';
	import { brokerService } from '@/services/broker/brokerService';
	import type { BackendInstitution } from '@/types/broker/broker';

	export let open = false;
	export let institution: BackendInstitution | null = null;
	export let onSuccess: () => void;

	let username = '';
	let password = '';
	let otp = '';

	let isLoading = false;
	let error: string | null = null;
	let requiresOtp = false;

	$: if (!open) {
		username = '';
		password = '';
		otp = '';
		requiresOtp = false;
		error = null;
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!institution || !username) return;

		isLoading = true;
		error = null;

		try {
			await brokerService.login(institution.id, {
				username,
				password: password ? password : undefined,
				otp: requiresOtp ? otp : undefined
			});
			open = false;
			onSuccess();
		} catch (e: any) {
			if (e.message === 'OTP_REQUIRED') {
				requiresOtp = true;
			} else if (e.message === 'INVALID_CREDENTIALS') {
				error = 'Invalid username or password';
			} else {
				error = 'Login failed. Please try again.';
			}
		} finally {
			isLoading = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-[425px]">
		<DialogHeader>
			<DialogTitle>Connect Broker</DialogTitle>
			<DialogDescription>
				{#if institution}
					Enter your credentials for {institution.name}
				{/if}
			</DialogDescription>
		</DialogHeader>

		<form on:submit={handleSubmit} class="grid gap-4 py-4">
			{#if error}
				<p class="text-sm text-red-500">{error}</p>
			{/if}

			<div class="grid gap-2">
				<Label for="username">Username / Email</Label>
				<Input id="username" type="text" bind:value={username} required />
			</div>

			<div class="grid gap-2">
				<Label for="password">Password</Label>
				<Input id="password" type="password" bind:value={password} required />
			</div>

			{#if requiresOtp}
				<div class="grid gap-2">
					<Label for="otp">2FA / OTP Code</Label>
					<Input id="otp" type="text" bind:value={otp} required autofocus />
				</div>
			{/if}

			<div class="flex justify-end pt-4">
				<Button
					type="submit"
					disabled={!institution || !username || !password || (requiresOtp && !otp) || isLoading}
				>
					{isLoading ? 'Connecting...' : 'Connect'}
				</Button>
			</div>
		</form>
	</DialogContent>
</Dialog>
