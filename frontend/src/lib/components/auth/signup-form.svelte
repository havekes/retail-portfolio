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
	import { resolve } from '$app/paths';
	import { enhance } from '$app/forms';

	let { form } = $props();
	const id = $props.id();
	let isLoading = $state(false);
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Sign Up</Card.Title>
		<Card.Description>Create an account to get started</Card.Description>
	</Card.Header>
	<Card.Content>
		<form
			method="POST"
			use:enhance={({ formData, cancel }) => {
				const password = formData.get('password');
				const confirmPassword = formData.get('confirmPassword');

				if (password !== confirmPassword) {
					if (!form) form = { email: formData.get('email') as string, message: '' };
					form.message = 'Passwords do not match.';
					cancel();
					return;
				}

				isLoading = true;
				return async ({ update }) => {
					isLoading = false;
					await update();
				};
			}}
		>
			<FieldGroup>
				<Field>
					<FieldLabel for="email-{id}">Email</FieldLabel>
					<Input
						id="email-{id}"
						name="email"
						type="email"
						placeholder="m@example.com"
						required
						value={form?.email ?? ''}
					/>
				</Field>
				<Field>
					<FieldLabel for="password-{id}">Password</FieldLabel>
					<Input id="password-{id}" name="password" type="password" required />
				</Field>
				<Field>
					<FieldLabel for="confirmPassword-{id}">Confirm Password</FieldLabel>
					<Input id="confirmPassword-{id}" name="confirmPassword" type="password" required />
				</Field>
				{#if form?.message}
					<p class="text-sm text-red-500">{form.message}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={isLoading}>
						{isLoading ? 'Signing up...' : 'Sign Up'}
					</Button>
					<FieldDescription class="text-center">
						Already have an account? <a href={resolve('/auth/login')}>Login</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
