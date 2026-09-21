<script lang="ts">
	import type { WaveDegree, WaveType } from '$lib/utils/finance/elliott-wave';
	import type { FibToolType } from '$lib/utils/finance/fibonacci';
	import {
		type ChartDrawingsService,
		getChartDrawingsService
	} from '$lib/services/ChartDrawingsService.svelte';
	import WaveIcon from '$lib/components/icons/wave-icon.svelte';
	import CorrectiveWaveIcon from '$lib/components/icons/corrective-wave-icon.svelte';
	import FibRetracementIcon from '$lib/components/icons/fib-retracement-icon.svelte';
	import FibExtensionIcon from '$lib/components/icons/fib-extension-icon.svelte';
	import HorizontalLineIcon from '$lib/components/icons/horizontal-line-icon.svelte';
	import LineIcon from '$lib/components/icons/line-icon.svelte';
	import Save from '@lucide/svelte/icons/save';
	import Check from '@lucide/svelte/icons/check';
	import Timeline from '@lucide/svelte/icons/timeline';
	import Ruler from '@lucide/svelte/icons/ruler';
	import Undo from '@lucide/svelte/icons/undo';
	import Redo from '@lucide/svelte/icons/redo';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';

	let {
		service: propService,
		activeWaveDegree: propActiveWaveDegree,
		activeWaveType: propActiveWaveType,
		isDrawingWave: propIsDrawingWave,
		activeFibTool: propActiveFibTool,
		isDrawingFib: propIsDrawingFib,
		isDrawingMeasure: propIsDrawingMeasure,
		isDrawingHorizontalLine: propIsDrawingHorizontalLine,
		isDrawingLine: propIsDrawingLine,
		isTimelineVisible: propIsTimelineVisible,
		canUndo: propCanUndo,
		canRedo: propCanRedo,
		onSelectWaveDegree,
		onSelectCorrectiveDegree,
		onToggleFib,
		onMeasureSelect,
		onHorizontalLineSelect,
		onLineSelect,
		onUndo,
		onRedo,
		onSave,
		saveFeedback: propSaveFeedback,
		onToggleTimeline
	}: {
		service?: ChartDrawingsService;
		activeWaveDegree?: WaveDegree;
		activeWaveType?: WaveType;
		isDrawingWave?: boolean;
		activeFibTool?: FibToolType | null;
		isDrawingFib?: boolean;
		isDrawingMeasure?: boolean;
		isDrawingHorizontalLine?: boolean;
		isDrawingLine?: boolean;
		isTimelineVisible?: boolean;
		canUndo?: boolean;
		canRedo?: boolean;
		onSelectWaveDegree?: (degree: WaveDegree, tool?: WaveType) => void;
		onSelectCorrectiveDegree?: (degree: WaveDegree) => void;
		onToggleFib?: (tool: FibToolType) => void;
		onMeasureSelect?: () => void;
		onHorizontalLineSelect?: () => void;
		onLineSelect?: () => void;
		onUndo?: () => void;
		onRedo?: () => void;
		onSave?: () => void;
		saveFeedback?: 'idle' | 'saved';
		onToggleTimeline?: () => void;
	} = $props();

	const contextService = getChartDrawingsService();
	const service = $derived(propService ?? contextService);

	let activeWaveDegree = $derived(
		service ? service.activeWaveDegree : (propActiveWaveDegree ?? 'cycle')
	);
	let activeWaveType = $derived(
		service ? service.activeWaveType : (propActiveWaveType ?? 'impulse')
	);
	let isDrawingWave = $derived(
		service ? service.isDrawingWaveEffective : (propIsDrawingWave ?? false)
	);
	let activeFibTool = $derived(service ? service.activeFibTool : (propActiveFibTool ?? null));
	let isDrawingFib = $derived(
		service ? service.isDrawingFibEffective : (propIsDrawingFib ?? false)
	);
	let isDrawingMeasure = $derived(
		service ? service.isDrawingMeasureEffective : (propIsDrawingMeasure ?? false)
	);
	let isDrawingHorizontalLine = $derived(
		service ? service.isDrawingHorizontalLineEffective : (propIsDrawingHorizontalLine ?? false)
	);
	let isDrawingLine = $derived(
		service ? service.isDrawingLineEffective : (propIsDrawingLine ?? false)
	);
	let isTimelineVisible = $derived(
		service ? service.isTimelineVisible : (propIsTimelineVisible ?? false)
	);
	let canUndo = $derived(service ? service.canUndo : (propCanUndo ?? false));
	let canRedo = $derived(service ? service.canRedo : (propCanRedo ?? false));
	let saveFeedback = $derived(service ? service.saveFeedback : (propSaveFeedback ?? 'idle'));

	function handleSelectWave(degree: WaveDegree, tool: WaveType) {
		if (tool === 'corrective' && onSelectCorrectiveDegree) {
			onSelectCorrectiveDegree(degree);
		} else if (onSelectWaveDegree) {
			onSelectWaveDegree(degree, tool);
		} else if (service) {
			service.selectWaveDegree(degree, tool);
		}
	}

	function handleToggleFib(tool: FibToolType) {
		if (onToggleFib) {
			onToggleFib(tool);
		} else if (service) {
			service.toggleFib(tool);
		}
	}

	function handleMeasureSelect() {
		if (onMeasureSelect) {
			onMeasureSelect();
		} else if (service) {
			service.toggleMeasure();
		}
	}

	function handleHorizontalLineSelect() {
		if (onHorizontalLineSelect) {
			onHorizontalLineSelect();
		} else if (service) {
			service.toggleHorizontalLine();
		}
	}

	function handleLineSelect() {
		if (onLineSelect) {
			onLineSelect();
		} else if (service) {
			service.toggleLine();
		}
	}

	function handleUndo() {
		if (onUndo) {
			onUndo();
		} else if (service) {
			void service.handleUndo();
		}
	}

	function handleRedo() {
		if (onRedo) {
			onRedo();
		} else if (service) {
			void service.handleRedo();
		}
	}

	function handleSave() {
		if (onSave) {
			onSave();
		} else if (service) {
			void service.handleSaveSnapshot();
		}
	}

	function handleToggleTimeline() {
		if (onToggleTimeline) {
			onToggleTimeline();
		} else if (service) {
			service.toggleTimeline();
		}
	}
</script>

<Tooltip.Provider>
	<div class="flex w-10 shrink-0 flex-col items-center gap-1 border-r bg-sidebar/50 p-1.5">
		<!-- Impulse Wave Dropdown -->
		<DropdownMenu.Root>
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props: tooltipProps })}
						<DropdownMenu.Trigger>
							{#snippet child({ props: triggerProps })}
								<button
									type="button"
									{...tooltipProps}
									{...triggerProps}
									class="rounded p-1.5 transition-colors {isDrawingWave &&
									activeWaveType === 'impulse'
										? 'bg-primary text-primary-foreground shadow-sm'
										: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
									aria-label="Impulse Wave"
									title="Impulse Wave"
								>
									<WaveIcon class="h-4 w-4" />
								</button>
							{/snippet}
						</DropdownMenu.Trigger>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content side="right">
					<p>Impulse Wave</p>
				</Tooltip.Content>
			</Tooltip.Root>
			<DropdownMenu.Content side="right" align="start" class="z-50 min-w-44">
				<DropdownMenu.Label>Degree</DropdownMenu.Label>
				<DropdownMenu.Separator />
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('cycle', 'impulse')}
					onclick={() => handleSelectWave('cycle', 'impulse')}
					class="flex items-center justify-between {activeWaveDegree === 'cycle' &&
					activeWaveType === 'impulse'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Cycle</span>
					<span class="text-muted-foreground">I</span>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('primary', 'impulse')}
					onclick={() => handleSelectWave('primary', 'impulse')}
					class="flex items-center justify-between {activeWaveDegree === 'primary' &&
					activeWaveType === 'impulse'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Primary</span>
					<span class="text-muted-foreground">①</span>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('intermediate', 'impulse')}
					onclick={() => handleSelectWave('intermediate', 'impulse')}
					class="flex items-center justify-between {activeWaveDegree === 'intermediate' &&
					activeWaveType === 'impulse'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Intermediate</span>
					<span class="text-muted-foreground">1</span>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>

		<!-- Corrective Wave Dropdown -->
		<DropdownMenu.Root>
			<Tooltip.Root>
				<Tooltip.Trigger>
					{#snippet child({ props: tooltipProps })}
						<DropdownMenu.Trigger>
							{#snippet child({ props: triggerProps })}
								<button
									type="button"
									{...tooltipProps}
									{...triggerProps}
									class="rounded p-1.5 transition-colors {isDrawingWave &&
									activeWaveType === 'corrective'
										? 'bg-primary text-primary-foreground shadow-sm'
										: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
									aria-label="Corrective Wave"
									title="Corrective Wave"
								>
									<CorrectiveWaveIcon class="h-4 w-4" />
								</button>
							{/snippet}
						</DropdownMenu.Trigger>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content side="right">
					<p>Corrective Wave</p>
				</Tooltip.Content>
			</Tooltip.Root>
			<DropdownMenu.Content side="right" align="start" class="z-50 min-w-44">
				<DropdownMenu.Label>Degree</DropdownMenu.Label>
				<DropdownMenu.Separator />
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('cycle', 'corrective')}
					onclick={() => handleSelectWave('cycle', 'corrective')}
					class="flex items-center justify-between {activeWaveDegree === 'cycle' &&
					activeWaveType === 'corrective'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Cycle</span>
					<span class="text-muted-foreground">A</span>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('primary', 'corrective')}
					onclick={() => handleSelectWave('primary', 'corrective')}
					class="flex items-center justify-between {activeWaveDegree === 'primary' &&
					activeWaveType === 'corrective'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Primary</span>
					<span class="text-muted-foreground">Ⓐ</span>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => handleSelectWave('intermediate', 'corrective')}
					onclick={() => handleSelectWave('intermediate', 'corrective')}
					class="flex items-center justify-between {activeWaveDegree === 'intermediate' &&
					activeWaveType === 'corrective'
						? 'font-medium'
						: ''}"
				>
					<span class="flex-1">Intermediate</span>
					<span class="text-muted-foreground">(A)</span>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>

		<!-- Fibonacci Retracement Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={() => handleToggleFib('retracement')}
						class="rounded p-1.5 transition-colors {isDrawingFib && activeFibTool === 'retracement'
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle Fib Retrace drawing"
						title="Fibonacci Retracement"
					>
						<FibRetracementIcon class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Fibonacci Retracement</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Fibonacci Extension Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={() => handleToggleFib('extension')}
						class="rounded p-1.5 transition-colors {isDrawingFib && activeFibTool === 'extension'
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle Fib Extend drawing"
						title="Fibonacci Extension"
					>
						<FibExtensionIcon class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Fibonacci Extension</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Measure Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={handleMeasureSelect}
						class="rounded p-1.5 transition-colors {isDrawingMeasure
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle Measure drawing"
						title="Measure"
					>
						<Ruler class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Measure</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Horizontal Line Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={handleHorizontalLineSelect}
						class="rounded p-1.5 transition-colors {isDrawingHorizontalLine
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle Horizontal Line drawing"
						title="Horizontal Line"
					>
						<HorizontalLineIcon class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Horizontal Line</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Free-form Line Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={handleLineSelect}
						class="rounded p-1.5 transition-colors {isDrawingLine
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle Line drawing"
						title="Line"
					>
						<LineIcon class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Line</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Undo Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						disabled={!canUndo}
						onclick={() => canUndo && handleUndo()}
						class="rounded p-1.5 transition-colors {!canUndo
							? 'cursor-not-allowed text-muted-foreground opacity-40'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Undo"
						title="Undo (Ctrl+Z / ⌘Z)"
					>
						<Undo class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Undo (Ctrl+Z / ⌘Z)</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Redo Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						disabled={!canRedo}
						onclick={() => canRedo && handleRedo()}
						class="rounded p-1.5 transition-colors {!canRedo
							? 'cursor-not-allowed text-muted-foreground opacity-40'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Redo"
						title="Redo (Ctrl+Y / ⌘Y)"
					>
						<Redo class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Redo (Ctrl+Y / ⌘Y)</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Save Snapshot Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={handleSave}
						class="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
						aria-label="Save snapshot"
						title={saveFeedback === 'saved' ? 'Saved' : 'Save snapshot'}
					>
						{#if saveFeedback === 'saved'}
							<Check class="h-4 w-4" />
						{:else}
							<Save class="h-4 w-4" />
						{/if}
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>{saveFeedback === 'saved' ? 'Saved' : 'Save snapshot'}</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<!-- Timeline Toggle Button -->
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props })}
					<button
						type="button"
						{...props}
						onclick={handleToggleTimeline}
						class="mt-auto rounded p-1.5 transition-colors {isTimelineVisible
							? 'bg-primary text-primary-foreground shadow-sm'
							: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
						aria-label="Toggle rewind timeline"
						title="Rewind Timeline"
					>
						<Timeline class="h-4 w-4" />
					</button>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content side="right">
				<p>Rewind Timeline</p>
			</Tooltip.Content>
		</Tooltip.Root>
	</div>
</Tooltip.Provider>
