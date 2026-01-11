<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { userStore } from '$lib/stores/userStore';
	import type { User } from '$lib/types/user';
	import { resolve } from '$app/paths';

	let { children } = $props();

	let user: User | null = $state(null);
	userStore.subscribe((authState) => (user = authState.user));

	const shouldRedirect = () => {
		const currentPath = page.url.pathname;
		return !user && currentPath !== '/login' && currentPath !== '/signup';
	};

	$effect(() => {
		if (shouldRedirect()) {
			goto(resolve('/login'));
		}
	});
</script>

<svelte:head>
	<!-- <link rel="icon" href={favicon} /> -->
</svelte:head>

<ModeWatcher />

{@render children()}
