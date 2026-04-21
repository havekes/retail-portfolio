<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { notesService } from '$lib/api/notesService';
	import NoteCreationDialog from './note-creation-dialog.svelte';
	import NoteViewDialog from './note-view-dialog.svelte';
	import NoteListItem from './note-list-item.svelte';
	import type { SecurityNote } from '$lib/api/notesService';
	import Plus from '@lucide/svelte/icons/plus';
	import { ModalState } from '@/utils/modal-state.svelte';
	import GroupTitle from '../group-title.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';

	let { securityId, expanded = $bindable(false) } = $props<{
		securityId: string;
		expanded?: boolean;
	}>();

	let notes = $state<SecurityNote[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);

	const createModal = new ModalState();
	const viewModal = new ModalState<SecurityNote>();
	const deleteConfirmationModal = new ModalState<number>();

	async function fetchNotes() {
		isLoading = true;
		error = null;
		try {
			notes = await notesService.getNotes(securityId);
			notes.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
		} catch (err) {
			const status = err && typeof err === 'object' && 'status' in err ? (err as any).status : null;
			if (status === 404) {
				notes = [];
			} else {
				error = err instanceof Error ? err.message : 'Failed to load notes';
				notes = [];
			}
		} finally {
			isLoading = false;
		}
	}

	async function handleDeleteConfirm() {
		const noteId = deleteConfirmationModal.data;
		if (noteId === null) return;
		try {
			await notesService.deleteNote(securityId, noteId);
			await fetchNotes();
			if (viewModal.data?.id === noteId) {
				viewModal.close();
			}
		} catch (err) {
			console.error('Failed to delete note:', err);
		}
	}

	function handleDeleteRequest(noteId: number) {
		deleteConfirmationModal.open(noteId);
	}

	$effect(() => {
		if (securityId) {
			fetchNotes();
		}
	});
</script>

<Sidebar.Group>
	<GroupTitle
		{expanded}
		onToggle={() => (expanded = !expanded)}
		actionIcon={Plus}
		onAction={() => createModal.open()}
	>
		Notes
	</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			{#if isLoading}
				<div class="space-y-2">
					{#each Array(3)}
						<Skeleton class="h-12 w-full" />
					{/each}
				</div>
			{:else if error}
				<SidebarError message={error} onretry={fetchNotes} />
			{:else if notes.length === 0}
				<div class="p-2 text-xs">No notes yet</div>
			{:else}
				<div class="space-y-1">
					{#each notes as note (note.id)}
						<NoteListItem
							{note}
							onclick={() => viewModal.open(note)}
							ondelete={() => handleDeleteRequest(note.id)}
						/>
					{/each}
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>

<NoteCreationDialog {securityId} modalState={createModal} onCreated={fetchNotes} />

{#if viewModal.data}
	<NoteViewDialog
		note={viewModal.data}
		{securityId}
		modalState={viewModal}
		onUpdated={fetchNotes}
		onDeleteRequest={() => handleDeleteRequest(viewModal.data!.id)}
	/>
{/if}

<ConfirmationModal
	bind:open={deleteConfirmationModal.isOpen}
	title="Delete Note"
	description="Are you sure you want to delete this note?"
	onconfirm={handleDeleteConfirm}
/>
