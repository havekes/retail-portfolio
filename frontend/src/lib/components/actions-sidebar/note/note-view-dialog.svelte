<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { notesService, type SecurityNote } from '$lib/api/notesService';
	import { ModalState } from '@/utils/modal-state.svelte';
	import { formatDate } from '@/utils/date';
	import { Textarea } from '@/components/ui/textarea/index.js';

	let props = $props<{
		note: SecurityNote;
		securityId: string;
		modalState: ModalState<SecurityNote>;
		onUpdated: () => void;
		onDeleteRequest: () => void;
	}>();

	let isEditing = $state(false);
	// svelte-ignore state_referenced_locally
	let editContent = $state(props.note.content);
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	async function handleUpdate() {
		if (!editContent.trim()) {
			error = 'Please enter note content';
			return;
		}

		isLoading = true;
		error = null;

		try {
			await notesService.updateNote(props.securityId, props.note.id, {
				content: editContent.trim()
			});
			isEditing = false;
			props.onUpdated();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to update note';
		} finally {
			isLoading = false;
		}
	}

	$effect(() => {
		if (props.modalState.isOpen) {
			editContent = props.note.content;
			isEditing = false;
			error = null;
		}
	});
</script>

<Dialog.Root bind:open={props.modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="max-w-lg">
			<Dialog.Header>
				<Dialog.Title>
					{isEditing ? 'Edit note' : 'View note'}
				</Dialog.Title>
				<Dialog.Description>
					Created on {formatDate(props.note.created_at)}
					{#if props.note.updated_at !== props.note.created_at}
						· Updated on {formatDate(props.note.updated_at)}
					{/if}
				</Dialog.Description>
			</Dialog.Header>

			<div class="mt-4">
				{#if error}
					<div class="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
						{error}
					</div>
				{/if}

				{#if isEditing}
					<Textarea
						bind:value={editContent}
						rows={10}
						class="min-h-30"
						placeholder="Enter note content..."
					/>
				{:else}
					<div
						class="max-h-[50vh] overflow-y-auto rounded-md bg-accent/50 p-4 text-sm leading-relaxed whitespace-pre-wrap"
					>
						{props.note.content}
					</div>
				{/if}
			</div>

			<Dialog.Footer class="mt-6 flex flex-row items-center justify-between sm:justify-between">
				<div class="flex gap-2">
					{#if !isEditing}
						<Button variant="destructive" onclick={props.onDeleteRequest}>Delete</Button>
					{/if}
				</div>
				<div class="flex gap-2">
					{#if isEditing}
						<Button variant="outline" onclick={() => (isEditing = false)} disabled={isLoading}>
							Cancel
						</Button>
						<Button onclick={handleUpdate} disabled={isLoading || !editContent.trim()}>
							{isLoading ? 'Saving...' : 'Save note'}
						</Button>
					{:else}
						<Button onclick={() => (isEditing = true)}>Edit</Button>
						<Button variant="outline" onclick={() => props.modalState.close()}>Close</Button>
					{/if}
				</div>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
