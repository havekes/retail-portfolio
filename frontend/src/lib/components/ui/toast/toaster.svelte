<script lang="ts">
	import { toast } from './toast.svelte.js';
	import CheckIcon from '@lucide/svelte/icons/check';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import InfoIcon from '@lucide/svelte/icons/info';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import XIcon from '@lucide/svelte/icons/x';
	import { cn } from '$lib/utils.js';

	let { class: className }: { class?: string } = $props();
</script>

<div
	class={cn(
		'fixed bottom-4 right-4 z-50 flex max-h-screen w-full max-w-sm flex-col-reverse gap-2 pointer-events-none p-4 sm:p-0',
		className
	)}
	data-testid="toaster"
>
	{#each toast.toasts as item (item.id)}
		<div
			role={item.type === 'error' ? 'alert' : 'status'}
			aria-live={item.type === 'error' ? 'assertive' : 'polite'}
			data-testid={`toast-${item.type}`}
			data-toast-id={item.id}
			class={cn(
				'pointer-events-auto flex items-start gap-3 rounded-lg border bg-card p-3 text-card-foreground shadow-lg transition-all',
				item.type === 'success' && 'border-green-500/30 text-card-foreground',
				item.type === 'error' && 'border-destructive/40 text-card-foreground',
				item.type === 'warning' && 'border-yellow-500/30 text-card-foreground',
				item.type === 'info' && 'border-border text-card-foreground'
			)}
		>
			<div class="mt-0.5 shrink-0">
				{#if item.type === 'success'}
					<CheckIcon class="h-4 w-4 text-green-500" data-testid="toast-icon-success" />
				{:else if item.type === 'error'}
					<CircleAlertIcon class="h-4 w-4 text-destructive" data-testid="toast-icon-error" />
				{:else if item.type === 'warning'}
					<TriangleAlertIcon class="h-4 w-4 text-yellow-500" data-testid="toast-icon-warning" />
				{:else}
					<InfoIcon class="h-4 w-4 text-sky-500" data-testid="toast-icon-info" />
				{/if}
			</div>

			<div class="flex-1 text-sm font-medium text-foreground">
				{item.message}
			</div>

			<button
				type="button"
				onclick={() => toast.remove(item.id)}
				class="shrink-0 rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
				aria-label="Dismiss toast"
			>
				<XIcon class="h-3.5 w-3.5" />
			</button>
		</div>
	{/each}
</div>
