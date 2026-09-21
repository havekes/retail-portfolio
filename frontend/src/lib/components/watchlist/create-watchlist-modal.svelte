<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	let { open = $bindable(false), onClose } = $props<{
		open?: boolean;
		onClose?: () => void;
	}>();

	const watchlistService = getWatchlistService();

	let name = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (open) {
			name = '';
			error = null;
		}
	});

	async function handleSubmit() {
		const trimmed = name.trim();
		if (!trimmed) {
			error = 'Watchlist name is required.';
			return;
		}

		isSubmitting = true;
		error = null;
		await watchlistService.createWatchlist(trimmed);

		if (watchlistService.error) {
			error = watchlistService.error;
			isSubmitting = false;
			return;
		}

		isSubmitting = false;
		open = false;
		name = '';
		onClose?.();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Create watchlist</Dialog.Title>
				<Dialog.Description>Enter a name for your new watchlist.</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4 py-2">
				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				<div class="space-y-2">
					<Label for="watchlist-name">Watchlist name</Label>
					<Input
						id="watchlist-name"
						bind:value={name}
						aria-label="Watchlist name"
						placeholder="Enter watchlist name"
						disabled={isSubmitting}
						onkeydown={(event) => {
							if (event.key === 'Enter') {
								event.preventDefault();
								void handleSubmit();
							}
						}}
					/>
				</div>
			</div>

			<Dialog.Footer>
				<Button variant="outline" disabled={isSubmitting} onclick={() => (open = false)}>
					Cancel
				</Button>
				<Button onclick={handleSubmit} disabled={isSubmitting || !name.trim()}>
					{#if isSubmitting}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
						Creating...
					{:else}
						Create
					{/if}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
