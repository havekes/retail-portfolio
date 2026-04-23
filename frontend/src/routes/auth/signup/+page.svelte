<script lang="ts">
	import SignupForm from '$lib/components/auth/signup-form.svelte';

	let { form } = $props();
</script>

<main class="grid h-screen w-full grid-cols-2 items-center">
	<div class="flex h-full items-center justify-center dark:bg-gray-900">
		<h1 class="text-3xl font-bold">Join us and start tracking</h1>
	</div>

	<SignupForm {form} />
</main>

