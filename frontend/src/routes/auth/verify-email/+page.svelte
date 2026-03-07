<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { authService } from '$lib/services/authService';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { CheckCircle2, XCircle, Loader2 } from '@lucide/svelte';
	import { resolve } from '$app/paths';

	let status: 'loading' | 'success' | 'error' = $state('loading');
	let message = $state('Verifying your email...');

	onMount(async () => {
		const token = page.url.searchParams.get('token');

		if (!token) {
			status = 'error';
			message = 'No verification token provided. Please check your email link.';
			return;
		}

		try {
			const response = await authService.verifyEmail(token);
			status = 'success';
			message = response.message || 'Your email has been successfully verified!';
		} catch (e) {
			status = 'error';
			message =
				(e instanceof Error ? e.message : '') ||
				'Verification failed. The link may be expired or invalid.';
		}
	});
</script>

<svelte:head>
	<title>Verify Email - Retail Portfolio</title>
</svelte:head>

<main class="flex min-h-screen flex-col items-center justify-center p-4">
	<Card.Root class="w-full max-w-md shadow-lg">
		{#if status === 'loading'}
			<Card.Header class="items-center pb-2 text-center">
				<Loader2 class="mb-4 h-12 w-12 animate-spin text-primary" />
				<Card.Title class="text-2xl font-semibold">Verifying...</Card.Title>
			</Card.Header>
			<Card.Content class="pb-6 text-center text-sm text-muted-foreground">
				{message}
			</Card.Content>
		{:else if status === 'success'}
			<Card.Header class="items-center pb-2 text-center">
				<CheckCircle2 class="mb-4 h-12 w-12 text-green-500" />
				<Card.Title class="text-2xl font-semibold text-green-500">Success!</Card.Title>
			</Card.Header>
			<Card.Content class="pb-6 text-center text-sm text-muted-foreground">
				{message}
			</Card.Content>
			<Card.Footer>
				<Button href={resolve('/auth/login')} class="w-full">Go to Login</Button>
			</Card.Footer>
		{:else}
			<Card.Header class="items-center pb-2 text-center">
				<XCircle class="mb-4 h-12 w-12 text-destructive" />
				<Card.Title class="text-2xl font-semibold text-destructive">Verification Failed</Card.Title>
			</Card.Header>
			<Card.Content class="pb-6 text-center text-sm text-muted-foreground">
				{message}
			</Card.Content>
			<Card.Footer class="flex-col gap-2">
				<Button href={resolve('/auth/signup')} variant="outline" class="w-full">
					Back to Signup
				</Button>
				<Button href={resolve('/auth/login')} variant="ghost" class="w-full">Go to Login</Button>
			</Card.Footer>
		{/if}
	</Card.Root>
</main>
