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
		} catch (e: any) {
			status = 'error';
			message = e.message || 'Verification failed. The link may be expired or invalid.';
		}
	});
</script>

<svelte:head>
	<title>Verify Email - Retail Portfolio</title>
</svelte:head>

<main class="flex min-h-screen flex-col items-center justify-center p-4">
	<Card.Root class="w-full max-w-md shadow-lg">
		{#if status === 'loading'}
			<Card.Header class="items-center text-center pb-2">
				<Loader2 class="h-12 w-12 animate-spin text-primary mb-4" />
				<Card.Title class="text-2xl font-semibold">Verifying...</Card.Title>
			</Card.Header>
			<Card.Content class="text-center text-sm text-muted-foreground pb-6">
				{message}
			</Card.Content>
		{:else if status === 'success'}
			<Card.Header class="items-center text-center pb-2">
				<CheckCircle2 class="h-12 w-12 text-green-500 mb-4" />
				<Card.Title class="text-2xl font-semibold text-green-500">Success!</Card.Title>
			</Card.Header>
			<Card.Content class="text-center text-sm text-muted-foreground pb-6">
				{message}
			</Card.Content>
			<Card.Footer>
				<Button href={resolve('/auth/login')} class="w-full">
					Go to Login
				</Button>
			</Card.Footer>
		{:else}
			<Card.Header class="items-center text-center pb-2">
				<XCircle class="h-12 w-12 text-destructive mb-4" />
				<Card.Title class="text-2xl font-semibold text-destructive">Verification Failed</Card.Title>
			</Card.Header>
			<Card.Content class="text-center text-sm text-muted-foreground pb-6">
				{message}
			</Card.Content>
			<Card.Footer class="flex-col gap-2">
				<Button href={resolve('/auth/signup')} variant="outline" class="w-full">
					Back to Signup
				</Button>
				<Button href={resolve('/auth/login')} variant="ghost" class="w-full">
					Go to Login
				</Button>
			</Card.Footer>
		{/if}
	</Card.Root>
</main>
