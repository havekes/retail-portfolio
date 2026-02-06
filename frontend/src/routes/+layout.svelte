<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { userStore } from '$lib/stores/userStore';
	import type { User } from '$lib/types/user';
	import { resolve } from '$app/paths';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import * as Command from '@/components/ui/command';
	import { debounce } from '@/utils';
	import { marketService } from '@/services/marketService';

	let { children } = $props();

	setBrokerService();

	let user: User | null = $state(null);
	userStore.subscribe((authState) => (user = authState.user));

	const shouldRedirect = () => {
		const currentPath = page.url.pathname;
		return (
			!user &&
			currentPath !== '/auth/login' &&
			currentPath !== '/auth/signup' &&
			currentPath !== '/auth/signup/confirmation' &&
			currentPath !== '/auth/verify-email'
		);
	};

	$effect(() => {
		if (shouldRedirect()) {
			goto(resolve('/auth/login'));
		}
	});

	let globalSearchOpen = $state(false);
	let globalSearchValue = $state('');

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			globalSearchOpen = !globalSearchOpen;
		}
	}

	$effect(() => {
		if (globalSearchValue.length > 0) {
			search(globalSearchValue);
		}
	});

	const search = debounce((query: string) => {
		marketService.search(query);
	}, 300);
</script>

<svelte:document onkeydown={handleKeydown} />

<svelte:head>
	<!-- <link rel="icon" href={favicon} /> -->
</svelte:head>

<ModeWatcher />

{@render children()}

<Command.Dialog bind:open={globalSearchOpen}>
	<Command.Input bind:value={globalSearchValue} placeholder="Search for a symbol..." />
	<Command.List>
		<Command.Empty>No results found.</Command.Empty>
		<Command.Group heading="Symbols">
			<Command.Item>
				<span>Calendar</span>
			</Command.Item>
			<Command.Item>
				<span>Search Emoji</span>
			</Command.Item>
			<Command.Item>
				<span>Calculator</span>
			</Command.Item>
		</Command.Group>
	</Command.List>
</Command.Dialog>
