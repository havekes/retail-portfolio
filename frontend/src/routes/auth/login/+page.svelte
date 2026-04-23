<script lang="ts">
	import LoginForm from '$lib/components/auth/login-form.svelte';

	let { form } = $props();
</script>

<main class="grid h-screen w-full grid-cols-2 items-center">
	<div class="flex h-full items-center justify-center dark:bg-gray-900">
		<h1 class="text-3xl font-bold">Welcome to a better portfolio</h1>
	</div>

	<LoginForm {form} />
</main>
