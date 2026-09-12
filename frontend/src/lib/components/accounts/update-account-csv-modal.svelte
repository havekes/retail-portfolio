<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { accountClient } from '$lib/api/accountClient';
	import type { Account } from '@/types/account';
	import type { ModalState } from '@/utils/modal-state.svelte';
	import Upload from '@lucide/svelte/icons/upload';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import FileSpreadsheet from '@lucide/svelte/icons/file-spreadsheet';

	let {
		account,
		modalState,
		onSuccess
	}: {
		account: Account;
		modalState: ModalState<void>;
		onSuccess?: () => void;
	} = $props();

	let selectedFile = $state<File | null>(null);
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);
	let isDragging = $state(false);

	const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

	$effect(() => {
		if (!modalState.isOpen) {
			resetState();
		}
	});

	function resetState() {
		selectedFile = null;
		error = null;
		isSubmitting = false;
		isDragging = false;
	}

	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
	}

	function validateAndSetFile(file: File) {
		error = null;
		if (!file.name.toLowerCase().endsWith('.csv')) {
			error = 'Please select a valid CSV file (.csv).';
			selectedFile = null;
			return;
		}

		if (file.size > MAX_FILE_SIZE) {
			error = 'File size exceeds 10MB limit.';
			selectedFile = null;
			return;
		}

		selectedFile = file;
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		validateAndSetFile(file);
		input.value = '';
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (!isSubmitting) {
			isDragging = true;
		}
	}

	function handleDragLeave(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
		if (isSubmitting) return;

		const file = e.dataTransfer?.files?.[0];
		if (file) {
			validateAndSetFile(file);
		}
	}

	async function handleUpload() {
		if (!selectedFile || isSubmitting) return;

		isSubmitting = true;
		error = null;

		try {
			await accountClient.syncAccountCsv(account.id, selectedFile);
			modalState.close();
			resetState();
			onSuccess?.();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to upload CSV file.';
		} finally {
			isSubmitting = false;
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter' && selectedFile && !isSubmitting) {
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
				<Dialog.Title>Update account from CSV</Dialog.Title>
				<Dialog.Description>
					Upload a CSV file to update positions for {account.name}.
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4 py-2">
				{#if error}
					<Alert.Root variant="destructive">
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				<div class="space-y-2">
					<Label for="csv-file-input">Select CSV file</Label>
					<div
						class="flex flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-colors {isDragging
							? 'border-primary bg-primary/5'
							: 'border-input hover:border-primary/50'}"
						ondragover={handleDragOver}
						ondragleave={handleDragLeave}
						ondrop={handleDrop}
						role="region"
						aria-label="CSV file dropzone"
					>
						<label for="csv-file-input" class="flex cursor-pointer flex-col items-center gap-2">
							<Upload class="h-8 w-8 text-muted-foreground" />
							<span class="text-sm font-medium text-foreground">
								Click to select or drag CSV file here
							</span>
							<span class="text-xs text-muted-foreground"> CSV files up to 10MB </span>
							<Input
								id="csv-file-input"
								type="file"
								accept=".csv,text/csv"
								onchange={handleFileSelect}
								class="hidden"
								disabled={isSubmitting}
							/>
						</label>
					</div>
				</div>

				{#if selectedFile}
					<div
						class="flex items-center justify-between rounded-md border border-input bg-accent/30 p-3"
						data-testid="selected-file-container"
					>
						<div class="flex items-center gap-2 truncate">
							<FileSpreadsheet class="h-4 w-4 shrink-0 text-muted-foreground" />
							<span class="truncate text-sm font-medium" data-testid="selected-file-name">
								{selectedFile.name}
							</span>
						</div>
						<span
							class="ml-2 shrink-0 text-xs text-muted-foreground"
							data-testid="selected-file-size"
						>
							{formatFileSize(selectedFile.size)}
						</span>
					</div>
				{/if}
			</div>

			<Dialog.Footer>
				<Button onclick={() => modalState.close()} variant="outline" disabled={isSubmitting}>
					Cancel
				</Button>
				<Button onclick={handleUpload} disabled={!selectedFile || isSubmitting}>
					{#if isSubmitting}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
						Uploading...
					{:else}
						Upload CSV
					{/if}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
