<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Save from '@lucide/svelte/icons/save';
	import Input from '../ui/input/input.svelte';
	import Button from '../ui/button/button.svelte';

	let { value = $bindable() }: { value: string } = $props();
	let isEditing = $state(false);
	let tempValue = $state(value);

	const save = (e: KeyboardEvent | MouseEvent) => {
		if (e instanceof KeyboardEvent && e.key !== 'Enter') {
			return;
		}

		e.preventDefault();
		value = tempValue;
		isEditing = false;
	};
</script>

<div class="group flex items-center">
	{#if isEditing}
		<Input bind:value={tempValue} onkeydown={save} />
		<Button
			variant="ghost"
			onclick={save}
			class="cursor-pointer text-muted-foreground hover:text-accent-foreground"
		>
			<Save size={14} />
		</Button>
	{:else}
		<h3 class="font-semibold">{value}</h3>
		<Button
			variant="ghost"
			onclick={() => (isEditing = !isEditing)}
			class="cursor-pointer text-muted-foreground hover:text-accent-foreground"
		>
			<Pencil
				size={14}
				class="hidden opacity-0 transition-opacity group-hover:block group-hover:opacity-100"
			/>
		</Button>
	{/if}
</div>
