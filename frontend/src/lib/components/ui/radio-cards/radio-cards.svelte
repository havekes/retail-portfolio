<script lang="ts" generics="T extends { id: string; name: string }">
	import { cn } from '$lib/utils';
	import type { Snippet } from 'svelte';

	interface Props {
		items: Array<T>;
		onSelect: (id: string) => void;
		selectedId?: string | null;
		class?: string;
		itemClass?: string;
		children?: Snippet<[T]>;
	}

	let {
		items = [],
		onSelect,
		selectedId = null,
		class: className = '',
		itemClass = '',
		children
	}: Props = $props();
</script>

<div class={cn('grid grid-cols-2 gap-4', className)}>
	{#each items as item (item.id)}
		<button
			type="button"
			class={cn(
				'flex cursor-pointer flex-col items-center justify-center rounded-lg border p-6 transition-all duration-200',
				'hover:-translate-y-1 hover:border-primary hover:shadow-md',
				'active:translate-y-0 active:scale-95 active:shadow-sm',
				selectedId === item.id ? 'border-primary ring-1 ring-primary' : '',
				itemClass
			)}
			onclick={() => onSelect(item.id)}
		>
			{#if children}
				{@render children(item)}
			{:else}
				<span class="text-center text-sm font-medium">{item.name}</span>
			{/if}
		</button>
	{/each}
	{#if items.length === 0}
		<div class="col-span-2 py-8 text-center text-muted-foreground">No items found.</div>
	{/if}
</div>
