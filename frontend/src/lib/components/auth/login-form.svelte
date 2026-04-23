<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { FieldGroup, Field, FieldDescription } from '$lib/components/ui/field/index.js';
	import { resolve } from '$app/paths';
	import { enhance } from '$app/forms';

	let { form } = $props();
	const id = $props.id();
	let isLoading = $state(false);
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Login</Card.Title>
		<Card.Description>Enter your email below to login to your account</Card.Description>
	</Card.Header>
	<Card.Content>
		<form
			method="POST"
			action="/auth/login"
			use:enhance={() => {
				isLoading = true;
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
						value={form?.email ?? ''}
					/>
				</Field>
				<Field>
					<Input id="password-{id}" name="password" type="password" placeholder="Password" required />
				</Field>
				{#if form?.message}
					<p class="text-sm text-red-500">{form.message}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={isLoading}>
						{isLoading ? 'Logging in...' : 'Login'}
					</Button>
					<FieldDescription class="text-center">
						Don't have an account? <a href={resolve('/auth/signup')}>Sign up for free</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
