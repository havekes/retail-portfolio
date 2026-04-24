<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { documentsService, type SecurityDocument } from '$lib/api/documentsService';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import FileDown from '@lucide/svelte/icons/file-down';
	import File from '@lucide/svelte/icons/file';
	import { ModalState } from '@/utils/modal-state.svelte';
	import { formatDate } from '@/utils/date';

	let { document, securityId, modalState, onDeleteRequest } = $props<{
		document: SecurityDocument;
		securityId: string;
		modalState: ModalState<SecurityDocument>;
		onDeleteRequest: () => void;
	}>();

	let error = $state<string | null>(null);
	let previewUrl = $state<string | null>(null);

	const isImage = $derived(document.file_type.startsWith('image/'));
	const isPdf = $derived(document.file_type === 'application/pdf');

	async function handleDownload() {
		try {
			const blob = await documentsService.downloadDocument(securityId, document.id);
			const url = URL.createObjectURL(blob);
			const link = window.document.createElement('a');
			link.href = url;
			link.download = document.filename;
			window.document.body.appendChild(link);
			link.click();
			window.document.body.removeChild(link);
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Failed to download document:', err);
		}
	}

	async function loadPreview() {
		if (!isImage && !isPdf) return;
		try {
			const blob = await documentsService.downloadDocument(securityId, document.id);
			previewUrl = URL.createObjectURL(blob);
		} catch (err) {
			console.error('Failed to load preview:', err);
		}
	}

	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
	}

	$effect(() => {
		if (modalState.isOpen) {
			loadPreview();
		}
		return () => {
			if (previewUrl) {
				URL.revokeObjectURL(previewUrl);
				previewUrl = null;
			}
		};
	});
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="max-w-2xl">
			<Dialog.Header>
				<Dialog.Title class="truncate">{document.filename}</Dialog.Title>
				<Dialog.Description>
					{formatFileSize(document.file_size)} · Uploaded on {formatDate(document.created_at)}
				</Dialog.Description>
			</Dialog.Header>

			<div class="mt-4 flex flex-col items-center justify-center rounded-md bg-accent/30 p-4">
				{#if error}
					<div class="mb-4 w-full rounded-md bg-destructive/10 p-3 text-sm text-destructive">
						{error}
					</div>
				{/if}

				{#if isImage && previewUrl}
					<img
						src={previewUrl}
						alt={document.filename}
						class="max-h-[50vh] max-w-full rounded shadow-sm"
					/>
				{:else if isPdf && previewUrl}
					<iframe title={document.filename} src={previewUrl} class="h-[50vh] w-full rounded"
					></iframe>
				{:else}
					<div class="flex flex-col items-center justify-center py-20 text-muted-foreground">
						{#if isPdf || isImage}
							<div class="animate-pulse">Loading preview...</div>
						{:else}
							<File class="mb-4 h-16 w-16" />
							<p>Preview not available for this file type ({document.file_type})</p>
						{/if}
					</div>
				{/if}
			</div>

			<Dialog.Footer class="mt-6 flex flex-row items-center justify-between sm:justify-between">
				<Button variant="destructive" size="sm" onclick={onDeleteRequest}>
					<Trash2 class="mr-2 h-4 w-4" />
					Delete
				</Button>
				<div class="flex gap-2">
					<Button variant="outline" size="sm" onclick={handleDownload}>
						<FileDown class="mr-2 h-4 w-4" />
						Download
					</Button>
					<Button variant="ghost" size="sm" onclick={() => modalState.close()}>Close</Button>
				</div>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
