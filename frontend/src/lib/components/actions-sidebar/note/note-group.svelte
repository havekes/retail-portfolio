<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { notesService } from '$lib/api/notesService';
	import { ApiError } from '$lib/api/apiClient';
	import NoteCreationDialog from './note-creation-dialog.svelte';
	import NoteViewDialog from './note-view-dialog.svelte';
	import NoteSummary from './note-summary.svelte';
	import NoteListItem from './note-list-item.svelte';
	import type { SecurityNote } from '$lib/api/notesService';
	import Plus from '@lucide/svelte/icons/plus';
	import { ModalState } from '@/utils/modal-state.svelte';
	import GroupTitle from '../group-title.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import ConfirmationModal from '$lib/components/ui/confirmation-modal/confirmation-modal.svelte';

	let {
		securityId,
		expanded = $bindable(false),
		pollIntervalMs,
		maxPollAttempts
	} = $props<{
		securityId: string;
		expanded?: boolean;
		/** Forwarded to the summary block so callers can shorten its post-mutation poll. */
		pollIntervalMs?: number;
		maxPollAttempts?: number;
	}>();

	let notes = $state<SecurityNote[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let summaryRef = $state<{ refresh: () => Promise<void> } | null>(null);

	const createModal = new ModalState();
	const viewModal = new ModalState<SecurityNote>();
	const deleteConfirmationModal = new ModalState<number>();

	async function fetchNotes() {
		isLoading = true;
		error = null;
		try {
			const res = await notesService.getNotes(securityId);
			notes = res.items;
			notes.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
		} catch (err) {
			const status = err instanceof ApiError ? err.status : null;
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
			await refreshAll();
			if (viewModal.data?.id === noteId) {
				viewModal.close();
			}
		} catch (err) {
			console.error('Failed to delete note:', err);
		}
	}

	// Every note mutation invalidates the AI summary, so both the list and the
	// summary block refresh together from one callback.
	async function refreshAll() {
		await fetchNotes();
		await summaryRef?.refresh();
	}

	function handleDeleteRequest(noteId: number) {
		deleteConfirmationModal.open(noteId);
	}

	function isTypingTarget(target: EventTarget | null): boolean {
		if (!(target instanceof HTMLElement)) return false;
		return (
			target.tagName === 'INPUT' ||
			target.tagName === 'TEXTAREA' ||
			target.tagName === 'SELECT' ||
			target.isContentEditable ||
			// jsdom does not implement `isContentEditable`, so also match the
			// attribute directly (same fallback as ChartDrawingsService).
			target.closest('[contenteditable="true"], [contenteditable=""]') !== null
		);
	}

	function isAnyModalOpen(): boolean {
		// Every modal in the app renders through the shared dialog wrapper, which
		// stamps `data-slot="dialog-content"` on bits-ui's content element.
		return Boolean(document.querySelector('[data-slot="dialog-content"][data-state="open"]'));
	}

	// Guards intentionally mirror the page-level and root-layout keydown handlers
	// so the two window listeners never double-handle a key: modifier combos and
	// keystrokes aimed at a typing surface or an already-open modal are ignored.
	function handleShortcutKeydown(event: KeyboardEvent) {
		if (event.metaKey || event.ctrlKey || event.altKey) return;
		if (isTypingTarget(event.target)) return;
		if (isAnyModalOpen()) return;

		if (event.key === 'n' || event.key === 'N') {
			event.preventDefault();
			createModal.open();
		}
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
			{#if notes.length > 0}
				<NoteSummary bind:this={summaryRef} {securityId} {pollIntervalMs} {maxPollAttempts} />
			{/if}

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

<svelte:window onkeydown={handleShortcutKeydown} />

<NoteCreationDialog {securityId} modalState={createModal} onCreated={refreshAll} />

{#if viewModal.data}
	<NoteViewDialog
		note={viewModal.data}
		{securityId}
		modalState={viewModal}
		onUpdated={refreshAll}
		onDeleteRequest={() => handleDeleteRequest(viewModal.data!.id)}
	/>
{/if}

<ConfirmationModal
	bind:open={deleteConfirmationModal.isOpen}
	title="Delete Note"
	description="Are you sure you want to delete this note?"
	onconfirm={handleDeleteConfirm}
/>
