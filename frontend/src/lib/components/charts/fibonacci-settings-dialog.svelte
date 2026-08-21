<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';
	import { untrack } from 'svelte';
	import {
		type FibToolType,
		type FibLevelConfig,
		DEFAULT_FIB_RETRACEMENT_LEVELS,
		DEFAULT_FIB_EXTENSION_LEVELS
	} from '$lib/utils/finance/fibonacci';

	let {
		open = $bindable(false),
		activeTool = 'retracement',
		retracementLevels = null,
		extensionLevels = null,
		hasActiveDrawing = true,
		disabled = false,
		onLevelsChange,
		onClose
	}: {
		open?: boolean;
		activeTool?: FibToolType | null;
		retracementLevels?: FibLevelConfig[] | null;
		extensionLevels?: FibLevelConfig[] | null;
		hasActiveDrawing?: boolean;
		disabled?: boolean;
		onLevelsChange?: (tool: FibToolType, levels: FibLevelConfig[]) => void;
		onClose?: () => void;
	} = $props();

	function cloneLevels(levels: FibLevelConfig[]): FibLevelConfig[] {
		return levels.map((lvl) => ({ ...lvl }));
	}

	function formatPercentage(ratio: number): string {
		const pct = (ratio * 100).toFixed(1);
		return `${pct}%`;
	}

	let activeTab = $state<FibToolType>(untrack(() => activeTool ?? 'retracement'));

	$effect(() => {
		if (activeTool) {
			activeTab = activeTool;
		}
	});

	let currentRetracementLevels = $state<FibLevelConfig[]>(
		untrack(() => cloneLevels(retracementLevels ?? DEFAULT_FIB_RETRACEMENT_LEVELS))
	);
	let currentExtensionLevels = $state<FibLevelConfig[]>(
		untrack(() => cloneLevels(extensionLevels ?? DEFAULT_FIB_EXTENSION_LEVELS))
	);

	let prevRetracementProp = $state<FibLevelConfig[] | null | undefined>(undefined);
	let prevExtensionProp = $state<FibLevelConfig[] | null | undefined>(undefined);

	$effect(() => {
		if (retracementLevels !== prevRetracementProp) {
			if (retracementLevels) {
				currentRetracementLevels = cloneLevels(retracementLevels);
			} else {
				currentRetracementLevels = cloneLevels(DEFAULT_FIB_RETRACEMENT_LEVELS);
			}
			prevRetracementProp = retracementLevels;
		}
	});

	$effect(() => {
		if (extensionLevels !== prevExtensionProp) {
			if (extensionLevels) {
				currentExtensionLevels = cloneLevels(extensionLevels);
			} else {
				currentExtensionLevels = cloneLevels(DEFAULT_FIB_EXTENSION_LEVELS);
			}
			prevExtensionProp = extensionLevels;
		}
	});

	const activeLevels = $derived(
		activeTab === 'retracement' ? currentRetracementLevels : currentExtensionLevels
	);

	const isInteractivityDisabled = $derived(disabled || !hasActiveDrawing);

	function handleToggleLevel(index: number) {
		if (isInteractivityDisabled) return;

		if (activeTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl, i) =>
				i === index ? { ...lvl, enabled: !(lvl.enabled ?? true) } : { ...lvl }
			);
			currentRetracementLevels = updated;
			onLevelsChange?.('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl, i) =>
				i === index ? { ...lvl, enabled: !(lvl.enabled ?? true) } : { ...lvl }
			);
			currentExtensionLevels = updated;
			onLevelsChange?.('extension', cloneLevels(updated));
		}
	}

	function handleEnableAll() {
		if (isInteractivityDisabled) return;

		if (activeTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl) => ({ ...lvl, enabled: true }));
			currentRetracementLevels = updated;
			onLevelsChange?.('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl) => ({ ...lvl, enabled: true }));
			currentExtensionLevels = updated;
			onLevelsChange?.('extension', cloneLevels(updated));
		}
	}

	function handleDisableAll() {
		if (isInteractivityDisabled) return;

		if (activeTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl) => ({ ...lvl, enabled: false }));
			currentRetracementLevels = updated;
			onLevelsChange?.('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl) => ({ ...lvl, enabled: false }));
			currentExtensionLevels = updated;
			onLevelsChange?.('extension', cloneLevels(updated));
		}
	}

	function handleResetToDefaults() {
		if (isInteractivityDisabled) return;

		if (activeTab === 'retracement') {
			const updated = cloneLevels(DEFAULT_FIB_RETRACEMENT_LEVELS);
			currentRetracementLevels = updated;
			onLevelsChange?.('retracement', cloneLevels(updated));
		} else {
			const updated = cloneLevels(DEFAULT_FIB_EXTENSION_LEVELS);
			currentExtensionLevels = updated;
			onLevelsChange?.('extension', cloneLevels(updated));
		}
	}

	function handleOpenChange(isOpen: boolean) {
		open = isOpen;
		if (!isOpen) {
			onClose?.();
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content class="w-full max-w-md">
		<Dialog.Header>
			<Dialog.Title>Fibonacci Settings</Dialog.Title>
			<Dialog.Description>
				Configure visible levels and colors for Fibonacci retracement and extension tools.
			</Dialog.Description>
		</Dialog.Header>

		<!-- Tool Type Tab Switcher -->
		<div
			class="flex items-center gap-1 rounded-lg border bg-muted/30 p-1"
			role="tablist"
			aria-label="Fibonacci tool type"
		>
			<button
				type="button"
				role="tab"
				aria-selected={activeTab === 'retracement'}
				aria-controls="fib-levels-panel"
				onclick={() => (activeTab = 'retracement')}
				class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeTab ===
				'retracement'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
			>
				Retracement
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={activeTab === 'extension'}
				aria-controls="fib-levels-panel"
				onclick={() => (activeTab = 'extension')}
				class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeTab ===
				'extension'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
			>
				Extension
			</button>
		</div>

		{#if isInteractivityDisabled}
			<div
				class="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-400"
				data-testid="fib-settings-disabled-banner"
			>
				<AlertCircle class="size-4 shrink-0" />
				<span>
					{#if disabled}
						Fibonacci settings are currently disabled.
					{:else}
						No active Fibonacci drawing selected on chart.
					{/if}
				</span>
			</div>
		{/if}

		<!-- Level List -->
		<div
			id="fib-levels-panel"
			role="tabpanel"
			class="max-h-64 space-y-1 divide-y divide-border/40 overflow-y-auto pr-1"
			data-testid="fib-levels-list"
		>
			{#each activeLevels as level, index (level.ratio)}
				<div
					class="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors {isInteractivityDisabled
						? 'cursor-not-allowed opacity-60'
						: 'cursor-pointer hover:bg-muted/40'}"
					data-testid={`fib-level-row-${level.ratio}`}
					onclick={() => handleToggleLevel(index)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							handleToggleLevel(index);
						}
					}}
					role="button"
					tabindex={isInteractivityDisabled ? -1 : 0}
					aria-label={`Toggle level ${level.ratio}`}
				>
					<div class="flex items-center gap-2.5">
						<Checkbox
							checked={level.enabled ?? true}
							onCheckedChange={() => handleToggleLevel(index)}
							disabled={isInteractivityDisabled}
							aria-label={`Toggle ${activeTab} level ${level.ratio}`}
							data-testid={`fib-checkbox-${level.ratio}`}
							onclick={(e) => e.stopPropagation()}
						/>
						<span
							class="size-3 shrink-0 rounded-full border border-border/50"
							style="background-color: {level.color || '#787B86'};"
							data-testid="fib-level-color-badge"
							aria-hidden="true"
						></span>
						<span class="font-mono text-sm font-medium" data-testid="fib-level-ratio">
							{level.ratio}
						</span>
					</div>
					<span class="font-mono text-xs text-muted-foreground" data-testid="fib-level-percentage">
						{formatPercentage(level.ratio)}
					</span>
				</div>
			{/each}
		</div>

		<!-- Batch Toolbar Actions -->
		<div class="flex flex-wrap items-center justify-between gap-2 border-t pt-2 text-xs">
			<div class="flex items-center gap-1.5">
				<Button
					variant="outline"
					size="sm"
					onclick={handleEnableAll}
					disabled={isInteractivityDisabled}
					class="h-7 px-2.5 text-xs"
				>
					Enable All
				</Button>
				<Button
					variant="outline"
					size="sm"
					onclick={handleDisableAll}
					disabled={isInteractivityDisabled}
					class="h-7 px-2.5 text-xs"
				>
					Disable All
				</Button>
			</div>
			<Button
				variant="ghost"
				size="sm"
				onclick={handleResetToDefaults}
				disabled={isInteractivityDisabled}
				class="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground"
			>
				<RotateCcw class="mr-1 size-3" />
				Reset to Defaults
			</Button>
		</div>

		<Dialog.Footer class="pt-2">
			<Button
				type="button"
				variant="secondary"
				size="sm"
				onclick={() => {
					open = false;
					onClose?.();
				}}
			>
				Close
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
