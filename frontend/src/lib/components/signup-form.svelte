<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import {
		FieldGroup,
		Field,
		FieldLabel,
		FieldDescription
	} from '$lib/components/ui/field/index.js';
	import { authService } from '$lib/services/authService';
	import { userStore } from '$lib/stores/userStore';
	const id = $props.id();
	let email = $state('');
	let password = $state('');
	let confirmPassword = $state('');
	let isLoading = $state(false);
	let error = $state<string | null>(null);
	async function handleSubmit(event: Event) {
		event.preventDefault();
		isLoading = true;
		error = null;
		if (password !== confirmPassword) {
			error = 'Passwords do not match.';
			isLoading = false;
			return;
		}
		try {
			const response = await authService.signup({ email, password });
			userStore.setUser(response.user, response.access_token);
		} catch (err) {
			error = 'Signup failed. Please try again.';
		} finally {
			isLoading = false;
		}
	}
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Sign Up</Card.Title>
		<Card.Description>Enter your email below to create your account</Card.Description>
	</Card.Header>
	<Card.Content>
		<form onsubmit={handleSubmit}>
			<FieldGroup>
				<Field>
					<FieldLabel for="email-{id}">Email</FieldLabel>
					<Input
						id="email-{id}"
						type="email"
						placeholder="m@example.com"
						required
						bind:value={email}
					/>
				</Field>
				<Field>
					<FieldLabel for="password-{id}">Password</FieldLabel>
					<Input id="password-{id}" type="password" required bind:value={password} />
				</Field>
				<Field>
					<FieldLabel for="confirmPassword-{id}">Confirm Password</FieldLabel>
					<Input id="confirmPassword-{id}" type="password" required bind:value={confirmPassword} />
				</Field>
				{#if error}
					<p class="text-sm text-red-500">{error}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={isLoading}>
						{isLoading ? 'Signing up...' : 'Sign Up'}
					</Button>
					<FieldDescription class="text-center">
						Already have an account? <a href="/login">Login</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
