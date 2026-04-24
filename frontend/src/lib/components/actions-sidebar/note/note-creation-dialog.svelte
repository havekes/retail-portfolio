<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { notesService } from '$lib/api/notesService';
	import type { SecurityNoteCreateRequest } from '$lib/api/notesService';
	import { ModalState } from '@/utils/modal-state.svelte';
	import { Button } from '@/components/ui/button/index.js';
	import { Textarea } from '@/components/ui/textarea/index.js';
	import { Kbd } from '@/components/ui/kbd';

	let { securityId, modalState, onCreated } = $props<{
		securityId: string;
		modalState: ModalState;
		onCreated?: () => void;
	}>();

	let content = $state('');
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	async function handleSubmit() {
		if (!content.trim()) {
			error = 'Please enter note content';
			return;
		}

		isLoading = true;
		error = null;

		try {
			const request: SecurityNoteCreateRequest = {
				content: content.trim()
			};
			await notesService.createNote(securityId, request);
			if (onCreated) onCreated();
			modalState.close();
			content = '';
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to create note';
		} finally {
			isLoading = false;
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content onkeydown={handleKeyDown}>
			<Dialog.Header>
				<Dialog.Title>Add note</Dialog.Title>
				<Dialog.Description>Your notes are private and only visible to you.</Dialog.Description>
			</Dialog.Header>

			<div class="">
				{#if error}
					<div
						class="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
					>
						{error}
					</div>
				{/if}

				<div class="space-y-2">
					<Textarea
						id="note-content"
						bind:value={content}
						placeholder="Enter your note here..."
						rows={6}
						class="min-h-30"
					/>
					<p class="text-xs text-muted-foreground">
						Press <Kbd>Enter</Kbd> to save, <Kbd>Shift+Enter</Kbd> for new line.
					</p>
				</div>
			</div>

			<Dialog.Footer>
				<Button onclick={() => modalState.close()} variant="outline" disabled={isLoading}>
					Cancel
				</Button>
				<Button onclick={handleSubmit} disabled={isLoading || !content.trim()}>
					{isLoading ? 'Saving...' : 'Save note'}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
