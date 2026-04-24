<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Root as ColorPicker } from '$lib/components/ui/color-picker/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	import type { IndicatorSettings } from '$lib/api/indicatorsService';

	let {
		open = $bindable(false),
		config = $bindable(null),
		onSave
	} = $props<{
		open: boolean;
		config: IndicatorSettings | null;
		onSave: (id: string, updatedConfig: IndicatorSettings) => void;
	}>();

	function handleSave() {
		if (config) {
			const { id, ...newConfig } = config;

			// Convert numbers
			if (newConfig.period) newConfig.period = Number(newConfig.period);
			if (newConfig.stdDev) newConfig.stdDev = Number(newConfig.stdDev);
			if (newConfig.fast) newConfig.fast = Number(newConfig.fast);
			if (newConfig.slow) newConfig.slow = Number(newConfig.slow);
			if (newConfig.signal) newConfig.signal = Number(newConfig.signal);

			onSave(id, newConfig);
		}
		open = false;
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>{config?.label} Settings</Dialog.Title>
		</Dialog.Header>

		{#if config}
			<div class="grid gap-4 py-4">
				<div class="grid grid-cols-4 items-center gap-2">
					<Label>Color</Label>
					<div class="col-span-3">
						<ColorPicker bind:value={config.color} class="w-full" />
					</div>
				</div>
				{#if config.id === 'rsi' || config.id === 'bb'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Period</Label>
						<Input type="number" bind:value={config.period} />
					</div>
				{/if}
				{#if config.id === 'bb'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Std Dev</Label>
						<Input type="number" bind:value={config.stdDev} />
					</div>
				{/if}
				{#if config.id === 'macd'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Fast</Label>
						<Input type="number" bind:value={config.fast} />
					</div>
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Slow</Label>
						<Input type="number" bind:value={config.slow} />
					</div>
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Signal</Label>
						<Input type="number" bind:value={config.signal} />
					</div>
				{/if}
			</div>
			<Dialog.Footer>
				<Button type="button" onclick={handleSave}>Save settings</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
