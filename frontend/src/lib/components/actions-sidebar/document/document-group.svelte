<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { documentsService } from '$lib/api/documentsService';
	import { ApiError } from '$lib/api/apiClient';
	import DocumentUploadDialog from './document-upload-dialog.svelte';
	import DocumentViewDialog from './document-view-dialog.svelte';
	import DocumentListItem from './document-list-item.svelte';
	import type { SecurityDocument } from '$lib/api/documentsService';
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

	let documents = $state<SecurityDocument[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);

	const uploadModal = new ModalState();
	const viewModal = new ModalState<SecurityDocument>();
	const deleteConfirmationModal = new ModalState<number>();

	async function fetchDocuments() {
		isLoading = true;
		error = null;
		try {
			documents = await documentsService.getDocuments(securityId);
		} catch (err) {
			const status = err instanceof ApiError ? err.status : null;
			if (status === 404) {
				documents = [];
			} else {
				error = err instanceof Error ? err.message : 'Failed to load documents';
				documents = [];
			}
		} finally {
			isLoading = false;
		}
	}

	async function handleDeleteConfirm() {
		const documentId = deleteConfirmationModal.data;
		if (documentId === null) return;
		try {
			await documentsService.deleteDocument(securityId, documentId);
			await fetchDocuments();
			if (viewModal.data?.id === documentId) {
				viewModal.close();
			}
		} catch (err) {
			console.error('Failed to delete document:', err);
		}
	}

	function handleDeleteRequest(documentId: number) {
		deleteConfirmationModal.open(documentId);
	}

	$effect(() => {
		if (securityId) {
			fetchDocuments();
		}
	});
</script>

<Sidebar.Group>
	<GroupTitle
		{expanded}
		onToggle={() => (expanded = !expanded)}
		actionIcon={Plus}
		onAction={() => uploadModal.open()}
	>
		Documents
	</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			<div>
				{#if isLoading}
					<div class="space-y-2">
						{#each Array(3)}
							<Skeleton class="h-10 w-full" />
						{/each}
					</div>
				{:else if error}
					<SidebarError message={error} onretry={fetchDocuments} />
				{:else if documents.length === 0}
					<div class="p-2 text-xs">No documents yet</div>
				{:else}
					<div class="space-y-1">
						{#each documents as doc (doc.id)}
							<DocumentListItem
								document={doc}
								onclick={() => viewModal.open(doc)}
								ondelete={() => handleDeleteRequest(doc.id)}
							/>
						{/each}
					</div>
				{/if}
			</div>
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>

<DocumentUploadDialog {securityId} modalState={uploadModal} onUploaded={fetchDocuments} />

{#if viewModal.data}
	<DocumentViewDialog
		document={viewModal.data}
		{securityId}
		modalState={viewModal}
		onDeleteRequest={() => handleDeleteRequest(viewModal.data!.id)}
	/>
{/if}

<ConfirmationModal
	bind:open={deleteConfirmationModal.isOpen}
	title="Delete Document"
	description="Are you sure you want to delete this document?"
	onconfirm={handleDeleteConfirm}
/>
