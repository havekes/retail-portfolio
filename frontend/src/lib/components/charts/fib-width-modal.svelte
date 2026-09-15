<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import type {
		FibToolType,
		FibRetracementDrawing,
		FibExtensionDrawing
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
	const PRESETS = [1, 1.5, 2, 3];

	let multiplier = $state<number>(1);
	let extendLines = $state<boolean>(false);

	$effect(() => {
		if (open) {
			multiplier =
				typeof drawing?.widthMultiplier === 'number' &&
				isFinite(drawing.widthMultiplier) &&
				drawing.widthMultiplier > 0
					? drawing.widthMultiplier
					: defaultMultiplier;
			extendLines = Boolean(drawing?.extendLines);
		}
	});

	function handlePreset(p: number) {
		multiplier = p;
	}

	function handleReset() {
		multiplier = defaultMultiplier;
		extendLines = false;
	}

	function handleCancel() {
		open = false;
		onClose?.();
	}

	function handleSave() {
		let val = Number(multiplier);
		if (isNaN(val) || !isFinite(val) || val <= 0) {
			val = defaultMultiplier;
		} else {
			val = Math.min(10, Math.max(0.1, Math.round(val * 100) / 100));
		}
		onSave?.(tool, val, extendLines);
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
			<!-- Width Multiplier Input -->
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<Label for="fib-width-multiplier" class="text-xs font-medium">Width Multiplier</Label>
					<span class="font-mono text-xs text-muted-foreground">{multiplier}x</span>
				</div>
				<Input
					id="fib-width-multiplier"
					type="number"
					min="0.1"
					max="10"
					step="0.1"
					placeholder={String(defaultMultiplier)}
					bind:value={multiplier}
					data-testid="fib-width-multiplier-input"
				/>
			</div>

			<!-- Multiplier Presets -->
			<div class="space-y-1.5">
				<Label class="text-xs text-muted-foreground">Quick Presets</Label>
				<div class="grid grid-cols-4 gap-1.5">
					{#each PRESETS as preset (preset)}
						<Button
							type="button"
							variant={Number(multiplier) === preset ? 'default' : 'outline'}
							size="sm"
							class="h-8 font-mono text-xs"
							onclick={() => handlePreset(preset)}
							data-testid={`preset-${preset}x`}
						>
							{preset}x
						</Button>
					{/each}
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
