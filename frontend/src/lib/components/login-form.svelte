<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { FieldGroup, Field, FieldDescription } from '$lib/components/ui/field/index.js';
	import { authService } from '$lib/services/authService';
	import { userStore } from '$lib/stores/userStore';
	import { resolve } from '$app/paths';

	const id = $props.id();

	let email = $state('');
	let password = $state('');
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	async function handleSubmit(event: Event) {
		event.preventDefault();
		isLoading = true;
		error = null;

		try {
			const response = await authService.login({ email, password });
			userStore.setUser(response.user, response.access_token);
			goto(resolve('/'));
		} catch {
			error = 'Login failed. Please check your credentials.';
		} finally {
			isLoading = false;
		}
	}
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Login</Card.Title>
		<Card.Description>Enter your email below to login to your account</Card.Description>
	</Card.Header>
	<Card.Content>
		<form onsubmit={handleSubmit}>
			<FieldGroup>
				<Field>
					<Input id="email-{id}" type="email" placeholder="Email" required bind:value={email} />
				</Field>
				<Field>
					<Input
						id="password-{id}"
						type="password"
						placeholder="Password"
						required
						bind:value={password}
					/>
				</Field>
				{#if error}
					<p class="text-sm text-red-500">{error}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={isLoading}>
						{isLoading ? 'Logging in...' : 'Login'}
					</Button>
					<FieldDescription class="text-center">
						Don't have an account? <a href={resolve('/signup')}>Sign up for free</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
