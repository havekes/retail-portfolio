<script lang="ts">
	import type { PriceAlert } from '$lib/api/alertsService';
	import { Bell, BellRing, Trash2 } from '@lucide/svelte';
	import { formatDate } from '@/utils/date';

	let { alert, ondelete } = $props<{
		alert: PriceAlert;
		ondelete: () => void;
	}>();

	const isTriggered = $derived(alert.triggered_at !== null);

	let isHovered = $state(false);

	const handleKeyDown = (e: KeyboardEvent) => {
		if (!isHovered) return;

		// Don't trigger if the user is typing in an input field
		const target = e.target as HTMLElement;
		if (
			target?.tagName === 'INPUT' ||
			target?.tagName === 'TEXTAREA' ||
			target?.isContentEditable
		) {
			return;
		}

		if (e.key === 'Backspace' || e.key === 'Delete') {
			e.preventDefault();
			ondelete();
		}
	};

	const handleDelete = () => {
		ondelete();
	};
</script>

<svelte:window onkeydown={handleKeyDown} />

<div
	role="button"
	tabindex="0"
	onmouseenter={() => (isHovered = true)}
	onmouseleave={() => (isHovered = false)}
	onfocus={() => (isHovered = true)}
	onblur={() => (isHovered = false)}
	class="group flex items-center justify-between rounded-md border border-sidebar-border p-2 text-left transition-all hover:border-sidebar-border/50 hover:bg-sidebar-accent/50"
>
	<div class="flex items-center gap-2">
		{#if isTriggered}
			<BellRing class="h-4 w-4 text-green-500" />
		{:else}
			<Bell class="h-4 w-4 text-sidebar-foreground/70" />
		{/if}
		<div class="space-y-0.5">
			<div class="text-sm font-medium">
				{alert.condition === 'above' ? 'Above' : 'Below'} ${Number(alert.target_price).toFixed(2)}
			</div>
			<div class="text-xs text-sidebar-foreground/70">
				Created {formatDate(alert.created_at)}
				{#if isTriggered && alert.triggered_at}
					· Triggered {formatDate(alert.triggered_at)}
				{/if}
			</div>
		</div>
	</div>
	<button
		onclick={handleDelete}
		class="rounded-md p-1 text-sidebar-foreground/70 opacity-0 transition-all group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
	>
		<Trash2 class="h-4 w-4" />
	</button>
</div>
