<script lang="ts">
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';

	export let title: string = '';
	export let subtitle: string = '';
	export let isLoading: boolean = false;
	export let error: string | null = null;
</script>

<div class="flex items-center border-b px-4 py-2">
	{#if isLoading}
		<div class="space-y-1">
			<Skeleton class="h-6 w-32" />
			<Skeleton class="h-4 w-48" />
		</div>
	{:else if error}
		<Alert.Root variant="destructive">
			<Alert.Description>{error}</Alert.Description>
		</Alert.Root>
	{:else}
		<div class="flex items-center gap-2">
			<h2 class="text-lg font-semibold">{title}</h2>
			{#if subtitle}
				<p class="text-sm text-muted-foreground">{subtitle}</p>
			{/if}
		</div>
	{/if}
	<slot name="actions" />
</div>
