<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { documentsService } from '$lib/api/documentsService';
	import Upload from '@lucide/svelte/icons/upload';
	import { ModalState } from '@/utils/modal-state.svelte';
	import { Button } from '@/components/ui/button/index.js';
	import { Input } from '@/components/ui/input/index.js';
	import { Label } from '@/components/ui/label/index.js';

	let { securityId, modalState, onUploaded } = $props<{
		securityId: string;
		modalState: ModalState;
		onUploaded?: () => void;
	}>();

	let selectedFile = $state<File | null>(null);
	let isUploading = $state(false);
	let error = $state<string | null>(null);

	const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'text/plain'];
	const maxFileSize = 10 * 1024 * 1024;

	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];

		if (!file) return;

		if (!allowedTypes.includes(file.type)) {
			error = 'Invalid file type. Allowed types: PDF, PNG, JPG, TXT';
			selectedFile = null;
			return;
		}

		if (file.size > maxFileSize) {
			error = 'File size exceeds 10MB limit';
			selectedFile = null;
			return;
		}

		error = null;
		selectedFile = file;
	}

	async function handleUpload() {
		if (!selectedFile || isUploading) return;

		isUploading = true;
		error = null;

		try {
			await documentsService.uploadDocument(securityId, selectedFile);
			if (onUploaded) onUploaded();
			modalState.close();
			resetState();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to upload document';
		} finally {
			isUploading = false;
		}
	}

	function resetState() {
		selectedFile = null;
		error = null;
		isUploading = false;
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter' && selectedFile && !isUploading) {
			e.preventDefault();
			handleUpload();
		}
	}
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content onkeydown={handleKeyDown}>
			<Dialog.Header>
				<Dialog.Title>Upload Document</Dialog.Title>
				<Dialog.Description>
					Upload a document for this security. Max file size: 10MB. Supported formats: PDF, PNG,
					JPG, TXT.
				</Dialog.Description>
			</Dialog.Header>

			<div class="grid gap-4 py-4">
				{#if error}
					<div
						class="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
					>
						{error}
					</div>
				{/if}

				<div class="space-y-2">
					<Label for="file-upload">Select File</Label>
					<div
						class="flex items-center justify-center rounded-md border-2 border-dashed border-input p-8 transition-colors hover:border-primary/50"
					>
						<Label class="flex cursor-pointer flex-col items-center gap-2">
							<Upload class="h-8 w-8 text-muted-foreground" />
							<span class="text-sm text-muted-foreground">Click to select or drag file here</span>
							<Input
								id="file-upload"
								type="file"
								accept=".pdf,.png,.jpg,.jpeg,.txt"
								onchange={handleFileSelect}
								class="hidden"
							/>
						</Label>
					</div>
				</div>

				{#if selectedFile}
					<div class="rounded-md border border-input bg-accent/30 p-3">
						<div class="flex items-center justify-between">
							<div class="flex-1 truncate text-sm font-medium">{selectedFile.name}</div>
							<div class="ml-2 text-sm text-muted-foreground">
								{formatFileSize(selectedFile.size)}
							</div>
						</div>
					</div>
				{/if}
			</div>

			<Dialog.Footer>
				<Button onclick={() => modalState.close()} variant="outline" disabled={isUploading}>
					Cancel
				</Button>
				<Button onclick={handleUpload} disabled={!selectedFile || isUploading}>
					{isUploading ? 'Uploading...' : 'Upload'}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
