<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import {
		type FibToolType,
		type FibRetracementDrawing,
		type FibExtensionDrawing,
		FIB_WIDTH_STOPS,
		FIB_WIDTH_STOP_LABELS,
		getClosestFibWidthIndex
	} from '$lib/utils/finance/fibonacci';

	let {
		open = $bindable(false),
		tool = 'retracement',
		drawing = null,
		onSave,
		onClose
	}: {
		open?: boolean;
		tool?: FibToolType;
		drawing?: FibRetracementDrawing | FibExtensionDrawing | null;
		onSave?: (tool: FibToolType, widthMultiplier: number | null, extendLines?: boolean) => void;
		onClose?: () => void;
	} = $props();

	const defaultMultiplier = $derived(tool === 'retracement' ? 1 : 2);
	const defaultIndex = $derived(getClosestFibWidthIndex(defaultMultiplier, defaultMultiplier));

	let sliderIndex = $state<number>(2);
	let extendLines = $state<boolean>(false);

	const multiplier = $derived(FIB_WIDTH_STOPS[sliderIndex] ?? defaultMultiplier);

	$effect(() => {
		if (open) {
			sliderIndex = getClosestFibWidthIndex(drawing?.widthMultiplier, defaultMultiplier);
			extendLines = Boolean(drawing?.extendLines);
		}
	});

	function handleSliderChange(idx: number) {
		sliderIndex = Math.max(0, Math.min(FIB_WIDTH_STOPS.length - 1, idx));
	}

	function handleReset() {
		sliderIndex = defaultIndex;
		extendLines = false;
	}

	function handleCancel() {
		open = false;
		onClose?.();
	}

	function handleSave() {
		onSave?.(tool, multiplier, extendLines);
		open = false;
		onClose?.();
	}

	function handleOpenChange(isOpen: boolean) {
		open = isOpen;
		if (!isOpen) {
			onClose?.();
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content class="w-full max-w-sm" data-testid="fib-width-modal">
		<Dialog.Header>
			<Dialog.Title data-testid="fib-width-modal-title">
				{tool === 'retracement' ? 'Fibonacci Retracement Width' : 'Fibonacci Extension Width'}
			</Dialog.Title>
			<Dialog.Description>
				Configure horizontal level line width and chart extension.
			</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-4 py-2">
			<!-- Width Multiplier Slider -->
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<Label for="fib-width-slider" class="text-xs font-medium">Width Multiplier</Label>
					<span
						class="font-mono text-xs font-semibold text-foreground"
						data-testid="fib-width-multiplier-display"
					>
						{FIB_WIDTH_STOP_LABELS[sliderIndex]}
					</span>
				</div>
				<div class="relative py-1">
					<input
						id="fib-width-slider"
						type="range"
						min="0"
						max="5"
						step="1"
						value={sliderIndex}
						oninput={(e) => handleSliderChange(Number(e.currentTarget.value))}
						class="w-full cursor-pointer accent-primary"
						data-testid="fib-width-slider"
						aria-label="Width Multiplier"
						aria-valuemin="0.25"
						aria-valuemax="3"
						aria-valuenow={multiplier}
						aria-valuetext={FIB_WIDTH_STOP_LABELS[sliderIndex]}
					/>
					<!-- Discrete Tick Marks -->
					<div
						class="mt-1 flex justify-between px-1"
						aria-hidden="true"
						data-testid="fib-width-ticks"
					>
						{#each FIB_WIDTH_STOPS as stop, idx (stop)}
							<div
								class="h-1.5 w-0.5 rounded-full {sliderIndex === idx
									? 'bg-primary'
									: 'bg-muted-foreground/40'}"
							></div>
						{/each}
					</div>
					<!-- Stop Labels / Quick Buttons -->
					<div
						class="mt-1 flex justify-between font-mono text-[11px] text-muted-foreground"
						data-testid="fib-width-stops"
					>
						{#each FIB_WIDTH_STOPS as stop, idx (stop)}
							<button
								type="button"
								class="cursor-pointer transition-colors hover:text-foreground focus:outline-none {sliderIndex ===
								idx
									? 'font-semibold text-primary'
									: ''}"
								onclick={() => handleSliderChange(idx)}
								data-testid={`preset-${stop}x`}
							>
								{FIB_WIDTH_STOP_LABELS[idx]}
							</button>
						{/each}
					</div>
				</div>
			</div>

			<!-- Full chart width checkbox -->
			<div class="flex items-center space-x-2 pt-1">
				<Checkbox
					id="fib-extend-lines"
					bind:checked={extendLines}
					data-testid="extend-lines-checkbox"
				/>
				<Label
					for="fib-extend-lines"
					class="cursor-pointer text-xs leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
				>
					Extend across full chart width
				</Label>
			</div>

			<!-- Reset to Default Button -->
			<div class="pt-1">
				<Button
					type="button"
					variant="ghost"
					size="sm"
					class="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
					onclick={handleReset}
					data-testid="reset-default-btn"
				>
					<RotateCcw class="mr-1.5 size-3" />
					Reset to Default ({defaultMultiplier}x)
				</Button>
			</div>
		</div>

		<Dialog.Footer class="gap-2 sm:gap-0">
			<Button
				type="button"
				variant="outline"
				size="sm"
				onclick={handleCancel}
				data-testid="cancel-btn"
			>
				Cancel
			</Button>
			<Button type="button" size="sm" onclick={handleSave} data-testid="save-btn">Save</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
