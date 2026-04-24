<script lang="ts">
	import type { SecurityDocument } from '$lib/api/documentsService';
	import { documentsService } from '$lib/api/documentsService';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import FileDown from '@lucide/svelte/icons/file-down';
	import FileText from '@lucide/svelte/icons/file-text';
	import Image from '@lucide/svelte/icons/image';
	import File from '@lucide/svelte/icons/file';
	import { formatDate } from '@/utils/date';

	let { document, onclick, ondelete } = $props<{
		document: SecurityDocument;
		onclick: () => void;
		ondelete: () => void;
	}>();

	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
	}

	function getIconForType(fileType: string) {
		if (fileType.startsWith('image/')) return Image;
		if (fileType === 'application/pdf') return FileText;
		if (fileType.startsWith('text/')) return FileText;
		return File;
	}

	async function handleDownload(e: MouseEvent) {
		e.stopPropagation();
		try {
			const blob = await documentsService.downloadDocument(document.security_id, document.id);
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

	function handleDelete(e: MouseEvent) {
		e.stopPropagation();
		ondelete();
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			onclick();
		} else if (e.key === 'Delete' || e.key === 'Backspace') {
			ondelete();
		}
	}

	const DocumentIcon = $derived(getIconForType(document.file_type));
</script>

<div
	role="button"
	tabindex="0"
	{onclick}
	onkeydown={handleKeyDown}
	class="group flex w-full cursor-pointer items-center justify-between rounded-md border border-sidebar-border p-2 text-left transition-all hover:border-sidebar-border/50 hover:bg-sidebar-accent/50 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
>
	<div class="flex min-w-0 flex-1 items-center gap-2">
		<DocumentIcon class="h-4 w-4 flex-shrink-0 text-sidebar-foreground/70" />
		<div class="min-w-0 flex-1">
			<div class="truncate text-sm font-medium">{document.filename}</div>
			<div class="text-xs text-sidebar-foreground/70">
				{formatFileSize(document.file_size)} · {formatDate(document.created_at)}
			</div>
		</div>
	</div>
	<div class="flex items-center gap-1">
		<button
			onclick={handleDownload}
			class="rounded-md p-1 text-sidebar-foreground/70 opacity-0 transition-all group-hover:opacity-100 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
			title="Download document"
		>
			<FileDown class="h-4 w-4" />
		</button>
		<button
			onclick={handleDelete}
			class="rounded-md p-1 text-sidebar-foreground/70 opacity-0 transition-all group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
			title="Delete document"
		>
			<Trash2 class="h-4 w-4" />
		</button>
	</div>
</div>
