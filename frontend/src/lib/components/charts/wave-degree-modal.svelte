<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import {
		ALL_WAVE_DEGREES,
		WAVE_DEGREE_LABELS,
		type WaveDegree
	} from '$lib/utils/finance/elliott-wave';

	let {
		open = $bindable(false),
		currentDegree = 'cycle',
		waveId = null,
		onSave,
		onClose
	}: {
		open?: boolean;
		currentDegree?: WaveDegree;
		waveId?: string | null;
		onSave?: (degree: WaveDegree, waveId?: string | null) => void;
		onClose?: () => void;
	} = $props();

	let selectedDegree = $state<WaveDegree>('cycle');

	$effect(() => {
		if (open) {
			selectedDegree = currentDegree;
		}
	});

	function handleCancel() {
		open = false;
		onClose?.();
	}

	function handleSave() {
		onSave?.(selectedDegree, waveId);
		open = false;
		onClose?.();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="sm:max-w-[420px]" data-testid="wave-degree-modal">
		<Dialog.Header>
			<Dialog.Title>Edit Wave Degree</Dialog.Title>
			<Dialog.Description>Select the Elliott wave degree for this wave count.</Dialog.Description>
		</Dialog.Header>

		<div class="py-3">
			<Label
				class="mb-2 block text-xs font-semibold tracking-wider text-muted-foreground uppercase"
			>
				Degree
			</Label>
			<div class="grid max-h-[300px] grid-cols-1 gap-1.5 overflow-y-auto pr-1">
				{#each ALL_WAVE_DEGREES as deg (deg)}
					<button
						type="button"
						role="radio"
						aria-checked={selectedDegree === deg}
						onclick={() => (selectedDegree = deg)}
						data-testid="degree-option-{deg}"
						class="flex items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors {selectedDegree ===
						deg
							? 'bg-primary font-medium text-primary-foreground'
							: 'text-foreground hover:bg-muted'}"
					>
						<span>{WAVE_DEGREE_LABELS[deg]}</span>
						{#if selectedDegree === deg}
							<span class="text-xs opacity-80">Selected</span>
						{/if}
					</button>
				{/each}
			</div>
		</div>

		<Dialog.Footer class="flex justify-end gap-2 border-t pt-3">
			<Button
				type="button"
				variant="outline"
				size="sm"
				onclick={handleCancel}
				data-testid="cancel-degree-btn"
			>
				Cancel
			</Button>
			<Button type="button" size="sm" onclick={handleSave} data-testid="save-degree-btn">
				Save Degree
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
