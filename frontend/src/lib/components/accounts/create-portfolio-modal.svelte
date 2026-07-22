<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { portfolioClient } from '$lib/api/portfolioClient';
	import type { ModalState } from '@/utils/modal-state.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import Loader2 from '@lucide/svelte/icons/loader-2';

	let { modalState, onCreated } = $props<{
		modalState: ModalState<string[]>;
		onCreated?: () => void;
	}>();

	let name = $state('');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (modalState.isOpen) {
			const today = new Date().toISOString().split('T')[0];
			name = `Portfolio - ${today}`;
			error = null;
		}
	});

	async function handleSubmit() {
		if (!name.trim()) {
			error = 'Portfolio name is required.';
			return;
		}
		if (!modalState.data || modalState.data.length === 0) {
			error = 'No accounts selected.';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			await portfolioClient.createPortfolio({
				name: name.trim(),
				accounts: modalState.data
			});
			if (onCreated) {
				onCreated();
			}
			modalState.close();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to create portfolio';
		} finally {
			isSubmitting = false;
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Create portfolio</Dialog.Title>
				<Dialog.Description>
					Do you want to create a portfolio from the selected accounts?
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4 py-2">
				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				<div class="space-y-2">
					<Label for="portfolio-name">Portfolio Name</Label>
					<Input
						id="portfolio-name"
						bind:value={name}
						placeholder="Enter portfolio name"
						disabled={isSubmitting}
						onkeydown={handleKeyDown}
					/>
				</div>
			</div>

			<Dialog.Footer>
				<Button onclick={() => modalState.close()} variant="outline" disabled={isSubmitting}>
					Cancel
				</Button>
				<Button onclick={handleSubmit} disabled={isSubmitting || !name.trim()}>
					{#if isSubmitting}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
						Creating...
					{:else}
						Create portfolio
					{/if}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
