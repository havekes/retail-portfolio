<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';
	import { untrack } from 'svelte';
	import type { WaveSettings } from '$lib/utils/finance/elliott-wave';
	import {
		type FibToolType,
		type FibLevelConfig,
		DEFAULT_FIB_RETRACEMENT_LEVELS,
		DEFAULT_FIB_EXTENSION_LEVELS
	} from '$lib/utils/finance/fibonacci';

	let {
		open = $bindable(false),
		initialSection = 'general',
		chartHideLabels = false,
		onSaveChartHideLabels,
		waveSettings = null,
		onSaveWaveSettings,
		activeTool = 'retracement',
		retracementLevels = null,
		extensionLevels = null,
		hasActiveDrawing = true,
		disabled = false,
		onFibLevelsChange,
		onLevelsChange,
		onClose
	}: {
		open?: boolean;
		initialSection?: 'general' | 'waves' | 'fibonacci';
		chartHideLabels?: boolean;
		onSaveChartHideLabels?: (hide: boolean) => void | Promise<void>;
		waveSettings?: WaveSettings | null;
		onSaveWaveSettings?: (settings: WaveSettings) => void | Promise<void>;
		activeTool?: FibToolType | null;
		retracementLevels?: FibLevelConfig[] | null;
		extensionLevels?: FibLevelConfig[] | null;
		hasActiveDrawing?: boolean;
		disabled?: boolean;
		onFibLevelsChange?: (tool: FibToolType, levels: FibLevelConfig[]) => void;
		onLevelsChange?: (tool: FibToolType, levels: FibLevelConfig[]) => void;
		onClose?: () => void;
	} = $props();

	let activeSection = $state<'general' | 'waves' | 'fibonacci'>(untrack(() => initialSection));

	// ---------------------------------------------------------------------------
	// General Section State & Handlers
	// ---------------------------------------------------------------------------
	let draftChartHideLabels = $state<boolean>(untrack(() => Boolean(chartHideLabels)));

	function syncGeneralFromProps() {
		draftChartHideLabels = Boolean(chartHideLabels);
	}

	let prevChartHideLabels: boolean | undefined;
	$effect(() => {
		if (chartHideLabels !== prevChartHideLabels) {
			syncGeneralFromProps();
			prevChartHideLabels = chartHideLabels;
		}
	});

	function handleCancelGeneral() {
		syncGeneralFromProps();
		open = false;
		onClose?.();
	}

	function handleSaveGeneral() {
		onSaveChartHideLabels?.(draftChartHideLabels);
		open = false;
		onClose?.();
	}

	// ---------------------------------------------------------------------------
	// Waves Section State & Handlers
	// ---------------------------------------------------------------------------
	let draftSnapToWicks = $state<boolean>(untrack(() => Boolean(waveSettings?.snap_to_wicks)));
	let cycleWave3Str = $state<string | number>(
		untrack(() => waveSettings?.alert_percents?.cycle?.wave3 ?? '')
	);
	let cycleWave5Str = $state<string | number>(
		untrack(() => waveSettings?.alert_percents?.cycle?.wave5 ?? '')
	);
	let primaryWave3Str = $state<string | number>(
		untrack(() => waveSettings?.alert_percents?.primary?.wave3 ?? '')
	);
	let primaryWave5Str = $state<string | number>(
		untrack(() => waveSettings?.alert_percents?.primary?.wave5 ?? '')
	);

	function syncWavesFromProps() {
		draftSnapToWicks = Boolean(waveSettings?.snap_to_wicks);
		cycleWave3Str = waveSettings?.alert_percents?.cycle?.wave3 ?? '';
		cycleWave5Str = waveSettings?.alert_percents?.cycle?.wave5 ?? '';
		primaryWave3Str = waveSettings?.alert_percents?.primary?.wave3 ?? '';
		primaryWave5Str = waveSettings?.alert_percents?.primary?.wave5 ?? '';
	}

	let prevWaveSettingsKey: string | undefined;
	$effect(() => {
		// Compare serialized snapshots, not proxy identities: `waveSettings` is a `$state`
		// proxy that gets re-created on parent re-renders, so `!==` on the object itself
		// trips Svelte's state_proxy_equality_mismatch and resyncs spuriously.
		const key = JSON.stringify(waveSettings) ?? '';
		if (key !== prevWaveSettingsKey) {
			syncWavesFromProps();
			prevWaveSettingsKey = key;
		}
	});

	function parsePercentInput(val: unknown): { num: number | null; error: string | null } {
		if (val === null || val === undefined) {
			return { num: null, error: null };
		}
		if (typeof val === 'number') {
			if (isNaN(val) || !isFinite(val)) {
				return { num: null, error: 'Percentages must be valid numbers.' };
			}
			if (val < 0) {
				return { num: null, error: 'Percentages cannot be negative.' };
			}
			return { num: val, error: null };
		}
		const str = String(val).trim();
		if (str === '') {
			return { num: null, error: null };
		}
		const n = Number(str);
		if (isNaN(n) || !isFinite(n)) {
			return { num: null, error: 'Percentages must be valid numbers.' };
		}
		if (n < 0) {
			return { num: null, error: 'Percentages cannot be negative.' };
		}
		return { num: n, error: null };
	}

	const parsedCycle3 = $derived(parsePercentInput(cycleWave3Str));
	const parsedCycle5 = $derived(parsePercentInput(cycleWave5Str));
	const parsedPrimary3 = $derived(parsePercentInput(primaryWave3Str));
	const parsedPrimary5 = $derived(parsePercentInput(primaryWave5Str));

	const wavesValidationError = $derived(
		parsedCycle3.error || parsedCycle5.error || parsedPrimary3.error || parsedPrimary5.error || null
	);

	const isWavesValid = $derived(wavesValidationError === null);

	function handleResetWavesToDefaults() {
		draftSnapToWicks = false;
		cycleWave3Str = '';
		cycleWave5Str = '';
		primaryWave3Str = '';
		primaryWave5Str = '';
	}

	function handleCancelWaves() {
		syncWavesFromProps();
		open = false;
		onClose?.();
	}

	function handleSaveWaves() {
		if (!isWavesValid) return;
		const updatedSettings: WaveSettings = {
			snap_to_wicks: draftSnapToWicks,
			alert_percents: {
				cycle: {
					wave3: parsedCycle3.num,
					wave5: parsedCycle5.num
				},
				primary: {
					wave3: parsedPrimary3.num,
					wave5: parsedPrimary5.num
				}
			}
		};
		onSaveWaveSettings?.(updatedSettings);
		open = false;
		onClose?.();
	}

	// ---------------------------------------------------------------------------
	// Fibonacci Section State & Handlers
	// ---------------------------------------------------------------------------
	function cloneLevels(levels: FibLevelConfig[]): FibLevelConfig[] {
		return levels.map((lvl) => ({ ...lvl }));
	}

	function formatPercentage(ratio: number): string {
		const pct = (ratio * 100).toFixed(1);
		return `${pct}%`;
	}

	let activeFibTab = $state<FibToolType>(untrack(() => activeTool ?? 'retracement'));

	$effect(() => {
		if (activeTool) {
			activeFibTab = activeTool;
		}
	});

	let currentRetracementLevels = $state<FibLevelConfig[]>(
		untrack(() => cloneLevels(retracementLevels ?? DEFAULT_FIB_RETRACEMENT_LEVELS))
	);
	let currentExtensionLevels = $state<FibLevelConfig[]>(
		untrack(() => cloneLevels(extensionLevels ?? DEFAULT_FIB_EXTENSION_LEVELS))
	);

	let prevRetracementKey: string | undefined;
	let prevExtensionKey: string | undefined;

	$effect(() => {
		const key = JSON.stringify(retracementLevels) ?? '';
		if (key !== prevRetracementKey) {
			if (retracementLevels) {
				currentRetracementLevels = cloneLevels(retracementLevels);
			} else {
				currentRetracementLevels = cloneLevels(DEFAULT_FIB_RETRACEMENT_LEVELS);
			}
			prevRetracementKey = key;
		}
	});

	$effect(() => {
		const key = JSON.stringify(extensionLevels) ?? '';
		if (key !== prevExtensionKey) {
			if (extensionLevels) {
				currentExtensionLevels = cloneLevels(extensionLevels);
			} else {
				currentExtensionLevels = cloneLevels(DEFAULT_FIB_EXTENSION_LEVELS);
			}
			prevExtensionKey = key;
		}
	});

	const activeFibLevels = $derived(
		activeFibTab === 'retracement' ? currentRetracementLevels : currentExtensionLevels
	);

	const isFibInteractivityDisabled = $derived(disabled || !hasActiveDrawing);

	function emitFibChange(tool: FibToolType, levels: FibLevelConfig[]) {
		onFibLevelsChange?.(tool, levels);
		onLevelsChange?.(tool, levels);
	}

	function handleToggleFibLevel(index: number) {
		if (isFibInteractivityDisabled) return;

		if (activeFibTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl, i) =>
				i === index ? { ...lvl, enabled: !(lvl.enabled ?? true) } : { ...lvl }
			);
			currentRetracementLevels = updated;
			emitFibChange('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl, i) =>
				i === index ? { ...lvl, enabled: !(lvl.enabled ?? true) } : { ...lvl }
			);
			currentExtensionLevels = updated;
			emitFibChange('extension', cloneLevels(updated));
		}
	}

	function handleEnableAllFib() {
		if (isFibInteractivityDisabled) return;

		if (activeFibTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl) => ({ ...lvl, enabled: true }));
			currentRetracementLevels = updated;
			emitFibChange('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl) => ({ ...lvl, enabled: true }));
			currentExtensionLevels = updated;
			emitFibChange('extension', cloneLevels(updated));
		}
	}

	function handleDisableAllFib() {
		if (isFibInteractivityDisabled) return;

		if (activeFibTab === 'retracement') {
			const updated = currentRetracementLevels.map((lvl) => ({ ...lvl, enabled: false }));
			currentRetracementLevels = updated;
			emitFibChange('retracement', cloneLevels(updated));
		} else {
			const updated = currentExtensionLevels.map((lvl) => ({ ...lvl, enabled: false }));
			currentExtensionLevels = updated;
			emitFibChange('extension', cloneLevels(updated));
		}
	}

	function handleResetFibToDefaults() {
		if (isFibInteractivityDisabled) return;

		if (activeFibTab === 'retracement') {
			const updated = cloneLevels(DEFAULT_FIB_RETRACEMENT_LEVELS);
			currentRetracementLevels = updated;
			emitFibChange('retracement', cloneLevels(updated));
		} else {
			const updated = cloneLevels(DEFAULT_FIB_EXTENSION_LEVELS);
			currentExtensionLevels = updated;
			emitFibChange('extension', cloneLevels(updated));
		}
	}

	function handleOpenChange(isOpen: boolean) {
		open = isOpen;
		if (!isOpen) {
			syncGeneralFromProps();
			syncWavesFromProps();
			onClose?.();
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content class="w-full max-w-md">
		<Dialog.Header>
			<Dialog.Title>Chart Settings</Dialog.Title>
			<Dialog.Description>
				Configure Elliott Wave alerts, snapping, and Fibonacci tool levels.
			</Dialog.Description>
		</Dialog.Header>

		<!-- Main Section Tab Switcher -->
		<div
			class="flex items-center gap-1 rounded-lg border bg-muted/30 p-1"
			role="tablist"
			aria-label="Chart settings section"
		>
			<button
				type="button"
				role="tab"
				aria-selected={activeSection === 'general'}
				aria-controls="general-settings-panel"
				onclick={() => (activeSection = 'general')}
				class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeSection ===
				'general'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
			>
				General
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={activeSection === 'waves'}
				aria-controls="waves-settings-panel"
				onclick={() => (activeSection = 'waves')}
				class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeSection ===
				'waves'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
			>
				Waves
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={activeSection === 'fibonacci'}
				aria-controls="fibonacci-settings-panel"
				onclick={() => (activeSection = 'fibonacci')}
				class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeSection ===
				'fibonacci'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
			>
				Fibonacci
			</button>
		</div>

		{#if activeSection === 'general'}
			<!-- General Panel -->
			<div
				id="general-settings-panel"
				role="tabpanel"
				class="space-y-4 py-1"
				data-testid="general-settings-panel"
			>
				<!-- Hide Labels Toggle -->
				<div class="flex items-start space-x-3 rounded-md border p-3">
					<Checkbox
						id="chart-hide-labels"
						checked={draftChartHideLabels}
						onCheckedChange={(checked) => (draftChartHideLabels = checked === true)}
						data-testid="hide-labels-checkbox"
						aria-label="Hide indicator labels"
					/>
					<div class="space-y-1 leading-none">
						<label
							for="chart-hide-labels"
							class="cursor-pointer text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
						>
							Hide indicator labels
						</label>
						<p class="text-xs text-muted-foreground">
							Hide right-axis price scale labels for indicators and average price lines.
						</p>
					</div>
				</div>

				<!-- General Footer Actions -->
				<div class="flex items-center justify-end gap-2 border-t pt-3">
					<Button
						type="button"
						variant="outline"
						size="sm"
						onclick={handleCancelGeneral}
						class="h-8 px-3 text-xs"
						data-testid="cancel-general-btn"
					>
						Cancel
					</Button>
					<Button
						type="button"
						size="sm"
						onclick={handleSaveGeneral}
						class="h-8 px-3 text-xs"
						data-testid="save-general-btn"
					>
						Save
					</Button>
				</div>
			</div>
		{:else if activeSection === 'waves'}
			<!-- Waves Panel -->
			<div
				id="waves-settings-panel"
				role="tabpanel"
				class="space-y-4 py-1"
				data-testid="waves-settings-panel"
			>
				<!-- Snap to Wicks Toggle -->
				<div class="flex items-start space-x-3 rounded-md border p-3">
					<Checkbox
						id="snap-to-wicks"
						checked={draftSnapToWicks}
						onCheckedChange={(checked) => (draftSnapToWicks = checked === true)}
						data-testid="snap-to-wicks-checkbox"
						aria-label="Snap to candle wicks"
					/>
					<div class="space-y-1 leading-none">
						<label
							for="snap-to-wicks"
							class="cursor-pointer text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
						>
							Snap to candle wicks
						</label>
						<p class="text-xs text-muted-foreground">
							Automatically snap wave point placements to nearest candle high/low wicks.
						</p>
					</div>
				</div>

				<!-- Alert Proximity Percents -->
				<div class="space-y-3">
					<div class="space-y-1">
						<h4 class="text-sm font-medium">Wave Target Alert Proximity (%)</h4>
						<p class="text-xs text-muted-foreground">
							Set proximity percentage for automated wave target price alerts. Leave blank to
							disable alerts.
						</p>
					</div>

					<!-- Cycle Degree -->
					<div class="space-y-3 rounded-md border p-3">
						<span class="text-xs font-semibold tracking-wider text-foreground uppercase"
							>Cycle Degree</span
						>
						<div class="grid grid-cols-2 gap-3">
							<div class="space-y-1.5">
								<Label for="cycle-wave3-percent" class="text-xs">Wave 3 (%)</Label>
								<Input
									id="cycle-wave3-percent"
									type="number"
									min="0"
									step="any"
									placeholder="Disabled"
									bind:value={cycleWave3Str}
									data-testid="cycle-wave3-input"
								/>
							</div>
							<div class="space-y-1.5">
								<Label for="cycle-wave5-percent" class="text-xs">Wave 5 (%)</Label>
								<Input
									id="cycle-wave5-percent"
									type="number"
									min="0"
									step="any"
									placeholder="Disabled"
									bind:value={cycleWave5Str}
									data-testid="cycle-wave5-input"
								/>
							</div>
						</div>
					</div>

					<!-- Primary Degree -->
					<div class="space-y-3 rounded-md border p-3">
						<span class="text-xs font-semibold tracking-wider text-foreground uppercase"
							>Primary Degree</span
						>
						<div class="grid grid-cols-2 gap-3">
							<div class="space-y-1.5">
								<Label for="primary-wave3-percent" class="text-xs">Wave 3 (%)</Label>
								<Input
									id="primary-wave3-percent"
									type="number"
									min="0"
									step="any"
									placeholder="Disabled"
									bind:value={primaryWave3Str}
									data-testid="primary-wave3-input"
								/>
							</div>
							<div class="space-y-1.5">
								<Label for="primary-wave5-percent" class="text-xs">Wave 5 (%)</Label>
								<Input
									id="primary-wave5-percent"
									type="number"
									min="0"
									step="any"
									placeholder="Disabled"
									bind:value={primaryWave5Str}
									data-testid="primary-wave5-input"
								/>
							</div>
						</div>
					</div>
				</div>

				<!-- Validation Error Feedback -->
				{#if wavesValidationError}
					<div
						class="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive"
						data-testid="waves-validation-error"
					>
						<AlertCircle class="size-4 shrink-0" />
						<span>{wavesValidationError}</span>
					</div>
				{/if}

				<!-- Waves Footer Actions -->
				<div class="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onclick={handleResetWavesToDefaults}
						class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
						data-testid="reset-waves-btn"
					>
						<RotateCcw class="mr-1 size-3" />
						Reset to Defaults
					</Button>
					<div class="flex items-center gap-2">
						<Button
							type="button"
							variant="outline"
							size="sm"
							onclick={handleCancelWaves}
							class="h-8 px-3 text-xs"
							data-testid="cancel-waves-btn"
						>
							Cancel
						</Button>
						<Button
							type="button"
							size="sm"
							disabled={!isWavesValid}
							onclick={handleSaveWaves}
							class="h-8 px-3 text-xs"
							data-testid="save-waves-btn"
						>
							Save
						</Button>
					</div>
				</div>
			</div>
		{:else}
			<!-- Fibonacci Panel -->
			<div
				id="fibonacci-settings-panel"
				role="tabpanel"
				class="space-y-3 py-1"
				data-testid="fibonacci-settings-panel"
			>
				<!-- Tool Type Tab Switcher -->
				<div
					class="flex items-center gap-1 rounded-lg border bg-muted/30 p-1"
					role="tablist"
					aria-label="Fibonacci tool type"
				>
					<button
						type="button"
						role="tab"
						aria-selected={activeFibTab === 'retracement'}
						aria-controls="fib-levels-panel"
						onclick={() => (activeFibTab = 'retracement')}
						class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeFibTab ===
						'retracement'
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
					>
						Retracement
					</button>
					<button
						type="button"
						role="tab"
						aria-selected={activeFibTab === 'extension'}
						aria-controls="fib-levels-panel"
						onclick={() => (activeFibTab = 'extension')}
						class="flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors {activeFibTab ===
						'extension'
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
					>
						Extension
					</button>
				</div>

				{#if isFibInteractivityDisabled}
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
					class="max-h-60 space-y-1 divide-y divide-border/40 overflow-y-auto pr-1"
					data-testid="fib-levels-list"
				>
					{#each activeFibLevels as level, index (level.ratio)}
						<div
							class="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors {isFibInteractivityDisabled
								? 'cursor-not-allowed opacity-60'
								: 'cursor-pointer hover:bg-muted/40'}"
							data-testid={`fib-level-row-${level.ratio}`}
							onclick={() => handleToggleFibLevel(index)}
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									handleToggleFibLevel(index);
								}
							}}
							role="button"
							tabindex={isFibInteractivityDisabled ? -1 : 0}
							aria-label={`Toggle level ${level.ratio}`}
						>
							<div class="flex items-center gap-2.5">
								<Checkbox
									checked={level.enabled ?? true}
									onCheckedChange={() => handleToggleFibLevel(index)}
									disabled={isFibInteractivityDisabled}
									aria-label={`Toggle ${activeFibTab} level ${level.ratio}`}
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
							<span
								class="font-mono text-xs text-muted-foreground"
								data-testid="fib-level-percentage"
							>
								{formatPercentage(level.ratio)}
							</span>
						</div>
					{/each}
				</div>

				<!-- Fibonacci Batch Actions -->
				<div class="flex flex-wrap items-center justify-between gap-2 border-t pt-2 text-xs">
					<div class="flex items-center gap-1.5">
						<Button
							variant="outline"
							size="sm"
							onclick={handleEnableAllFib}
							disabled={isFibInteractivityDisabled}
							class="h-7 px-2.5 text-xs"
						>
							Enable All
						</Button>
						<Button
							variant="outline"
							size="sm"
							onclick={handleDisableAllFib}
							disabled={isFibInteractivityDisabled}
							class="h-7 px-2.5 text-xs"
						>
							Disable All
						</Button>
					</div>
					<Button
						variant="ghost"
						size="sm"
						onclick={handleResetFibToDefaults}
						disabled={isFibInteractivityDisabled}
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
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
