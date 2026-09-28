<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Save from '@lucide/svelte/icons/save';
	import Input from '../ui/input/input.svelte';
	import Button from '../ui/button/button.svelte';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import { cn } from '$lib/utils.js';
	import { tick } from 'svelte';

	let {
		value = $bindable(),
		isEditing = $bindable(false),
		showEditButton = true,
		linkClass = '',
		onSave,
		containerClass = '',
		textClass = 'font-semibold text-lg',
		href,
		action,
		name = 'name',
		id
	}: {
		value: string;
		isEditing?: boolean;
		showEditButton?: boolean;
		linkClass?: string;
		onSave?: (newValue: string) => void;
		containerClass?: string;
		textClass?: string;
		href?: string;
		action?: string;
		name?: string;
		id?: string;
	} = $props();

	let tempValue = $state(value);
	let inputRef = $state<HTMLInputElement | null>(null);
	let wasEditing = false;

	$effect(() => {
		if (isEditing && !wasEditing) {
			tempValue = value;
			void tick().then(() => {
				inputRef?.focus();
				inputRef?.select();
			});
		} else if (!isEditing) {
			tempValue = value;
		}
		wasEditing = isEditing;
	});

	const save = (e: KeyboardEvent | MouseEvent) => {
		if (e instanceof KeyboardEvent) {
			if (e.key === 'Escape') {
				isEditing = false;
				return;
			}
			if (e.key !== 'Enter') {
				return;
			}
		}

		if (!action) {
			e.preventDefault();
			if (value !== tempValue) {
				value = tempValue;
				if (onSave) onSave(tempValue);
			}
			isEditing = false;
		}
	};

	const toggleEdit = () => {
		isEditing = !isEditing;
	};
</script>

<div class="flex items-center gap-2 {containerClass}">
	{#if isEditing}
		{#if action}
			<form
				method="POST"
				{action}
				use:enhance={() => {
					return async ({ result, update }) => {
						if (result.type === 'success') {
							value = tempValue;
							if (onSave) onSave(tempValue);
							isEditing = false;
						}
						await update();
					};
				}}
				class="flex items-center gap-2"
			>
				<Input
					bind:ref={inputRef}
					{name}
					bind:value={tempValue}
					onkeydown={(e) => e.key === 'Escape' && (isEditing = false)}
					autofocus
				/>
				{#if id}
					<input type="hidden" name="id" value={id} />
				{/if}
				<Button
					type="submit"
					variant="ghost"
					size="icon-sm"
					class="shrink-0 cursor-pointer text-muted-foreground hover:text-accent-foreground"
				>
					<Save size={14} />
				</Button>
			</form>
		{:else}
			<Input bind:ref={inputRef} bind:value={tempValue} onkeydown={save} autofocus />
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={save}
				class="shrink-0 cursor-pointer text-muted-foreground hover:text-accent-foreground"
			>
				<Save size={14} />
			</Button>
		{/if}
	{:else}
		{#if href}
			<a href={resolve(href as unknown as '/')} class={cn('hover:underline', textClass, linkClass)}>
				{value}
			</a>
		{:else}
			<div class={cn(textClass, linkClass)}>{value}</div>
		{/if}
		{#if showEditButton}
			<Button
				variant="ghost"
				size="icon-sm"
				onclick={toggleEdit}
				class="shrink-0 cursor-pointer text-muted-foreground hover:text-foreground"
			>
				<Pencil size={14} />
			</Button>
		{/if}
	{/if}
</div>
