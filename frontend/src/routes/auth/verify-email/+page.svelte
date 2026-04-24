<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { CheckCircle2, XCircle } from '@lucide/svelte';
	import { resolve } from '$app/paths';

	let { data } = $props();
</script>

<svelte:head>
	<title>Verify Email - Retail Portfolio</title>
</svelte:head>

<main class="flex min-h-screen flex-col items-center justify-center p-4">
	<Card.Root class="w-full max-w-md shadow-lg">
		{#if data.status === 'success'}
			<Card.Header class="items-center pb-2 text-center">
				<CheckCircle2 class="mb-4 h-12 w-12 text-green-500" />
				<Card.Title class="text-2xl font-semibold text-green-500">Success!</Card.Title>
			</Card.Header>
			<Card.Content class="pb-6 text-center text-sm text-muted-foreground">
				{data.message}
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
				{data.message}
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
