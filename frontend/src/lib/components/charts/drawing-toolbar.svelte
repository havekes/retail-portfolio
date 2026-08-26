<script lang="ts">
	import type { WaveDegree, WaveType } from '$lib/utils/finance/elliott-wave';
	import type { FibToolType } from '$lib/utils/finance/fibonacci';
	import WaveIcon from '$lib/components/icons/wave-icon.svelte';
	import CorrectiveWaveIcon from '$lib/components/icons/corrective-wave-icon.svelte';
	import FibRetracementIcon from '$lib/components/icons/fib-retracement-icon.svelte';
	import FibExtensionIcon from '$lib/components/icons/fib-extension-icon.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';

	let {
		activeWaveDegree = 'cycle',
		activeWaveType = 'impulse',
		isDrawingWave = false,
		activeFibTool = null,
		isDrawingFib = false,
		onSelectWaveDegree,
		onSelectCorrectiveDegree,
		onToggleFib
	}: {
		activeWaveDegree?: WaveDegree;
		activeWaveType?: WaveType;
		isDrawingWave?: boolean;
		activeFibTool?: FibToolType | null;
		isDrawingFib?: boolean;
		onSelectWaveDegree?: (degree: WaveDegree, tool?: WaveType) => void;
		onSelectCorrectiveDegree?: (degree: WaveDegree) => void;
		onToggleFib?: (tool: FibToolType) => void;
	} = $props();

	function handleSelectWave(degree: WaveDegree, tool: WaveType) {
		if (tool === 'corrective' && onSelectCorrectiveDegree) {
			onSelectCorrectiveDegree(degree);
		} else {
			onSelectWaveDegree?.(degree, tool);
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
						onclick={() => onToggleFib?.('retracement')}
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
						onclick={() => onToggleFib?.('extension')}
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
	</div>
</Tooltip.Provider>
