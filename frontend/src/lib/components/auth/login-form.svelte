<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { FieldGroup, Field, FieldDescription } from '$lib/components/ui/field/index.js';
	import { resolve } from '$app/paths';
	import { LoginFormState } from './login-form.svelte.js';

	const id = $props.id();
	const state = new LoginFormState();
</script>

<Card.Root class="mx-auto w-full max-w-sm">
	<Card.Header>
		<Card.Title class="text-2xl">Login</Card.Title>
		<Card.Description>Enter your email below to login to your account</Card.Description>
	</Card.Header>
	<Card.Content>
		<form onsubmit={state.handleSubmit}>
			<FieldGroup>
				<Field>
					<Input
						id="email-{id}"
						type="email"
						placeholder="Email"
						required
						bind:value={state.email}
					/>
				</Field>
				<Field>
					<Input
						id="password-{id}"
						type="password"
						placeholder="Password"
						required
						bind:value={state.password}
					/>
				</Field>
				{#if state.error}
					<p class="text-sm text-red-500">{state.error}</p>
				{/if}
				<Field>
					<Button type="submit" class="w-full" disabled={state.isLoading}>
						{state.isLoading ? 'Logging in...' : 'Login'}
					</Button>
					<FieldDescription class="text-center">
						Don't have an account? <a href={resolve('/auth/signup')}>Sign up for free</a>
					</FieldDescription>
				</Field>
			</FieldGroup>
		</form>
	</Card.Content>
</Card.Root>
