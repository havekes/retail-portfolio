<script lang="ts">
	import type { SecurityNote } from '$lib/api/notesService';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { formatDate } from '@/utils/date';
	import { StickyNote } from '@lucide/svelte';

	let { note, onclick, ondelete } = $props<{
		note: SecurityNote;
		onclick: () => void;
		ondelete: () => void;
	}>();

	const preview = $derived(
		note.title ||
			(note.content.length > 100 ? note.content.substring(0, 100) + '...' : note.content)
	);

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
</script>

<div
	role="button"
	tabindex="0"
	{onclick}
	onkeydown={handleKeyDown}
	class="group flex w-full cursor-pointer items-center space-x-2 rounded-md border border-sidebar-border p-2 text-left transition-all hover:border-sidebar-border/50 hover:bg-sidebar-accent/50"
>
	<StickyNote class="h-4 w-4 flex-shrink-0 text-sidebar-foreground/70" />

	<div class="flex-1 space-y-1 pr-2">
		<div class="text-xs text-muted-foreground">{formatDate(note.created_at)}</div>
		<div class="line-clamp-2 text-sm">{preview}</div>
	</div>
	<button
		onclick={handleDelete}
		class="rounded-md p-1 text-muted-foreground opacity-0 transition-all group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
		title="Delete note"
	>
		<Trash2 class="h-4 w-4" />
	</button>
</div>
