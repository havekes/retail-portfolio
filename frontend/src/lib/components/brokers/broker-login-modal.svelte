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
	import { BrokerLoginModalState } from './broker-login-modal.svelte.js';
	import type { BackendInstitution } from '@/types/broker/broker';

	let {
		open = $bindable(false),
		institution,
		onSuccess
	} = $props<{
		open: boolean;
		institution: BackendInstitution | null;
		onSuccess: () => void;
	}>();

	const state = new BrokerLoginModalState(
		() => institution,
		() => onSuccess(),
		() => (open = false)
	);

	$effect(() => {
		if (!open) {
			state.reset();
		}
	});
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

		<form onsubmit={state.handleSubmit} class="grid gap-4 py-4">
			{#if state.error}
				<p class="text-sm text-red-500">{state.error}</p>
			{/if}

			<div class="grid gap-2">
				<Label for="username">Username / Email</Label>
				<Input id="username" type="text" bind:value={state.username} required />
			</div>

			<div class="grid gap-2">
				<Label for="password">Password</Label>
				<Input id="password" type="password" bind:value={state.password} required />
			</div>

			{#if state.requiresOtp}
				<div class="grid gap-2">
					<Label for="otp">2FA / OTP Code</Label>
					<Input id="otp" type="text" bind:value={state.otp} required autofocus />
				</div>
			{/if}

			<div class="flex justify-end pt-4">
				<Button
					type="submit"
					disabled={!institution ||
						!state.username ||
						!state.password ||
						(state.requiresOtp && !state.otp) ||
						state.isLoading}
				>
					{state.isLoading ? 'Connecting...' : 'Connect'}
				</Button>
			</div>
		</form>
	</DialogContent>
</Dialog>
