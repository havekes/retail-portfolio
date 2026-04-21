<script lang="ts">
	import AlertCircle from '@lucide/svelte/icons/alert-circle';

	let { message = 'Failed to load data', onretry } = $props<{
		message?: string;
		onretry?: () => void;
	}>();
</script>

<div
	class="flex flex-col items-center justify-center space-y-2 rounded-md border border-destructive/20 bg-destructive/10 p-4 text-center"
>
	<AlertCircle class="h-6 w-6 text-destructive" />
	<p class="text-sm text-destructive">{message}</p>
	{#if onretry}
		<button onclick={onretry} class="text-xs font-medium text-destructive hover:underline"
			>Try again</button
		>
	{/if}
</div>
