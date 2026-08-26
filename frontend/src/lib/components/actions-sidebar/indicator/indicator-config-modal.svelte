<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Popover from '$lib/components/ui/popover/index.js';
	import { Root as ColorPicker } from '$lib/components/ui/color-picker/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';

	import type { IndicatorSettings } from '$lib/api/indicatorsService';

	let {
		open = $bindable(false),
		config = $bindable(null),
		onSave,
		onReset
	} = $props<{
		open: boolean;
		config: IndicatorSettings | null;
		onSave: (id: string, updatedConfig: IndicatorSettings) => void;
		onReset: (id: string) => void;
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

	function handleReset() {
		if (config) {
			const { id } = config;
			onReset(id);
		}
		// Deliberately does NOT close the dialog — the restored values stay visible.
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
					<div class="col-span-3 flex justify-end">
						<Popover.Root>
							<Popover.Trigger>
								{#snippet child({ props })}
									<button
										{...props}
										type="button"
										style:background-color={config.color}
										aria-label={`Change color (current color: ${config.color})`}
										data-testid="indicator-color-swatch"
										class="size-9 rounded-md border"
									></button>
								{/snippet}
							</Popover.Trigger>
							<!-- bottom-end: popover's right edge aligns with the swatch's right edge, extending leftward below the button -->
							<Popover.Content
								class="w-auto bg-transparent p-0 shadow-none ring-0"
								side="bottom"
								align="end"
							>
								<ColorPicker bind:value={config.color} />
							</Popover.Content>
						</Popover.Root>
					</div>
				</div>
				{#if config.id === 'rsi' || config.id === 'bb'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Period</Label>
						<div class="col-span-3 flex justify-end">
							<Input type="number" class="w-24" bind:value={config.period} />
						</div>
					</div>
				{/if}
				{#if config.id === 'bb'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Std Dev</Label>
						<div class="col-span-3 flex justify-end">
							<Input type="number" class="w-24" bind:value={config.stdDev} />
						</div>
					</div>
				{/if}
				{#if config.id === 'macd'}
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Fast</Label>
						<div class="col-span-3 flex justify-end">
							<Input type="number" class="w-24" bind:value={config.fast} />
						</div>
					</div>
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Slow</Label>
						<div class="col-span-3 flex justify-end">
							<Input type="number" class="w-24" bind:value={config.slow} />
						</div>
					</div>
					<div class="grid grid-cols-4 items-center gap-2">
						<Label>Signal</Label>
						<div class="col-span-3 flex justify-end">
							<Input type="number" class="w-24" bind:value={config.signal} />
						</div>
					</div>
				{/if}
			</div>
			<Dialog.Footer class="sm:justify-between">
				<Button
					type="button"
					variant="ghost"
					size="sm"
					onclick={handleReset}
					class="text-muted-foreground hover:text-foreground"
					data-testid="reset-indicator-btn"
				>
					<RotateCcw class="mr-1 size-3" />
					Reset to defaults
				</Button>
				<Button type="button" onclick={handleSave}>Save settings</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
