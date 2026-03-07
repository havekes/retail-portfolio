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
	import { SignupFormState } from './signup-form.svelte.js';

	const id = $props.id();
	const state = new SignupFormState();
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Sign Up</Card.Title>
		<Card.Description>Create an account to get started</Card.Description>
	</Card.Header>
	<Card.Content>
		<form onsubmit={state.handleSubmit}>
			<FieldGroup>
				<Field>
					<FieldLabel for="email-{id}">Email</FieldLabel>
					<Input
						id="email-{id}"
						type="email"
						placeholder="m@example.com"
						required
						bind:value={state.email}
					/>
				</Field>
				<Field>
					<FieldLabel for="password-{id}">Password</FieldLabel>
					<Input id="password-{id}" type="password" required bind:value={state.password} />
				</Field>
				<Field>
					<FieldLabel for="confirmPassword-{id}">Confirm Password</FieldLabel>
					<Input
						id="confirmPassword-{id}"
						type="password"
						required
						bind:value={state.confirmPassword}
					/>
				</Field>
				{#if state.error}
					<p class="text-sm text-red-500">{state.error}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={state.isLoading}>
						{state.isLoading ? 'Signing up...' : 'Sign Up'}
					</Button>
					<FieldDescription class="text-center">
						Already have an account? <a href={resolve('/auth/login')}>Login</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
