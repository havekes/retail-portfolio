<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { resolve } from '$app/paths';
	import { Button } from '$lib/components/ui/button/index.js';
</script>

<main class="grid h-screen w-full grid-cols-2 items-center">
	<div class="flex h-full items-center justify-center dark:bg-gray-900">
		<h1 class="text-3xl font-bold">Welcome to a better portfolio</h1>
	</div>

	<div class="flex flex-col items-center justify-center p-8">
		<Card.Root class="mx-auto w-full max-w-sm">
			<Card.Header>
				<Card.Title class="text-center text-2xl">Check your email</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-4 text-center">
				<p class="text-muted-foreground">
					We've sent a confirmation link to your email address. Please follow the link to activate
					your account.
				</p>
				<Button href={resolve('/auth/login')} variant="outline" class="w-full">
					Back to Login
				</Button>
			</Card.Content>
		</Card.Root>
	</div>
</main>
