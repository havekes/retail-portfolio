<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { ChevronDown } from '@lucide/svelte';
	import type { Component, Snippet } from 'svelte';

	let { expanded, onToggle, actionIcon, onAction, children } = $props<{
		expanded: boolean;
		onToggle: () => void;
		actionIcon?: Component;
		onAction?: () => void;
		children: Snippet;
	}>();

	const Icon = $derived(actionIcon);
</script>

<Sidebar.GroupLabel>
	<button onclick={onToggle} class="flex items-center gap-2 text-sm hover:text-foreground">
		<ChevronDown class="h-4 w-4 transition-transform {expanded ? '' : '-rotate-90'}" />
		{@render children()}
	</button>
</Sidebar.GroupLabel>

{#if actionIcon}
	<Sidebar.GroupAction>
		<button
			onclick={onAction}
			class="flex h-5 w-5 items-center justify-center rounded-md border border-sidebar-border bg-sidebar-accent text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
			aria-label="Add price alert"
		>
			<Icon class="h-3 w-3"></Icon>
		</button>
	</Sidebar.GroupAction>
{/if}
