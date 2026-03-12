<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Save from '@lucide/svelte/icons/save';
	import Input from '../ui/input/input.svelte';
	import Button from '../ui/button/button.svelte';

	let {
		value = $bindable(),
		onSave,
		containerClass = '',
		textClass = 'font-semibold text-lg'
	}: {
		value: string;
		onSave?: (newValue: string) => void;
		containerClass?: string;
		textClass?: string;
	} = $props();
	let isEditing = $state(false);
	let tempValue = $state(value);

	const save = (e: KeyboardEvent | MouseEvent) => {
		if (e instanceof KeyboardEvent && e.key !== 'Enter') {
			return;
		}

		e.preventDefault();
		if (value !== tempValue) {
			value = tempValue;
			if (onSave) onSave(tempValue);
		}
		isEditing = false;
	};
</script>

<div class="flex items-center gap-2 {containerClass}">
	{#if isEditing}
		<Input bind:value={tempValue} onkeydown={save} />
		<Button
			variant="ghost"
			size="icon-sm"
			onclick={save}
			class="shrink-0 cursor-pointer text-muted-foreground hover:text-accent-foreground"
		>
			<Save size={14} />
		</Button>
	{:else}
		<div class={textClass}>{value}</div>
		<Button
			variant="ghost"
			size="icon-sm"
			onclick={() => (isEditing = !isEditing)}
			class="shrink-0 cursor-pointer text-muted-foreground hover:text-foreground"
		>
			<Pencil size={14} />
		</Button>
	{/if}
</div>
