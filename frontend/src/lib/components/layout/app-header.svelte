<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';

	let {
		title = '',
		subtitle = '',
		isLoading = false,
		error = null,
		titleSlot,
		actions
	}: {
		title?: string;
		subtitle?: string;
		isLoading?: boolean;
		error?: string | null;
		titleSlot?: import('svelte').Snippet;
		actions?: import('svelte').Snippet;
	} = $props();
</script>

<div class="flex h-[49px] items-center border-b px-4 py-2">
	{#if isLoading}
		<div class="flex items-center gap-2">
			<Skeleton class="h-6 w-32" />
			<Skeleton class="h-4 w-48" />
		</div>
	{:else if error}
		<Alert.Root variant="destructive">
			<Alert.Description>{error}</Alert.Description>
		</Alert.Root>
	{:else}
		<div class="flex items-center gap-2">
			{#if titleSlot}
				{@render titleSlot()}
			{:else}
				<h2 class="text-lg font-semibold">{title}</h2>
			{/if}
			{#if subtitle}
				<p class="text-sm text-muted-foreground">{subtitle}</p>
			{/if}
		</div>
	{/if}
	{#if actions}
		<div class="ml-auto">
			{@render actions()}
		</div>
	{/if}
</div>
