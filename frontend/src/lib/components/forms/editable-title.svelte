<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Save from '@lucide/svelte/icons/save';
	import Input from '../ui/input/input.svelte';
	import Button from '../ui/button/button.svelte';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';

	let {
		value = $bindable(),
		onSave,
		containerClass = '',
		textClass = 'font-semibold text-lg',
		href,
		action,
		name = 'name',
		id
	}: {
		value: string;
		onSave?: (newValue: string) => void;
		containerClass?: string;
		textClass?: string;
		href?: string;
		action?: string;
		name?: string;
		id?: string;
	} = $props();
	let isEditing = $state(false);
	let tempValue = $state(value);

	const save = (e: KeyboardEvent | MouseEvent) => {
		if (e instanceof KeyboardEvent && e.key !== 'Enter') {
			return;
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
		if (!isEditing) {
			tempValue = value;
		}
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
							isEditing = false;
						}
						await update();
					};
				}}
				class="flex items-center gap-2"
			>
				<Input
					{name}
					bind:value={tempValue}
					onkeydown={(e) => e.key === 'Escape' && (isEditing = false)}
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
			<Input bind:value={tempValue} onkeydown={save} />
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
			<a href={resolve(href as unknown as '/')} class="hover:underline {textClass}">
				{value}
			</a>
		{:else}
			<div class={textClass}>{value}</div>
		{/if}
		<Button
			variant="ghost"
			size="icon-sm"
			onclick={toggleEdit}
			class="shrink-0 cursor-pointer text-muted-foreground hover:text-foreground"
		>
			<Pencil size={14} />
		</Button>
	{/if}
</div>
