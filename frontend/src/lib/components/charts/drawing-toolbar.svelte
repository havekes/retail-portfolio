<script lang="ts">
	import type { WaveDegree } from '$lib/utils/finance/elliott-wave';
	import type { FibToolType } from '$lib/utils/finance/fibonacci';
	import WaveIcon from '$lib/components/icons/wave-icon.svelte';
	import FibRetracementIcon from '$lib/components/icons/fib-retracement-icon.svelte';
	import FibExtensionIcon from '$lib/components/icons/fib-extension-icon.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';

	let {
		activeWaveDegree = 'cycle',
		isDrawingWave = false,
		activeFibTool = null,
		isDrawingFib = false,
		onSelectWaveDegree,
		onToggleFib
	}: {
		activeWaveDegree?: WaveDegree;
		isDrawingWave?: boolean;
		activeFibTool?: FibToolType | null;
		isDrawingFib?: boolean;
		onSelectWaveDegree?: (degree: WaveDegree) => void;
		onToggleFib?: (tool: FibToolType) => void;
	} = $props();
</script>

<div class="flex w-10 shrink-0 flex-col items-center gap-1 border-r bg-sidebar/50 p-1.5">
	<DropdownMenu.Root>
		<DropdownMenu.Trigger>
			{#snippet child({ props })}
				<button
					type="button"
					{...props}
					class="rounded p-1.5 transition-colors {isDrawingWave
						? 'bg-primary text-primary-foreground shadow-sm'
						: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
					aria-label="Elliott Wave"
					title="Elliott Wave"
				>
					<WaveIcon class="h-4 w-4" />
				</button>
			{/snippet}
		</DropdownMenu.Trigger>
		<DropdownMenu.Content side="right" align="start" class="z-50 min-w-36">
			<DropdownMenu.Item
				onSelect={() => onSelectWaveDegree?.('cycle')}
				onclick={() => onSelectWaveDegree?.('cycle')}
				class={activeWaveDegree === 'cycle' ? 'font-medium' : ''}
			>
				Cycle Degree
			</DropdownMenu.Item>
			<DropdownMenu.Item
				onSelect={() => onSelectWaveDegree?.('primary')}
				onclick={() => onSelectWaveDegree?.('primary')}
				class={activeWaveDegree === 'primary' ? 'font-medium' : ''}
			>
				Primary Degree
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	</DropdownMenu.Root>

	<button
		type="button"
		onclick={() => onToggleFib?.('retracement')}
		class="rounded p-1.5 transition-colors {isDrawingFib && activeFibTool === 'retracement'
			? 'bg-primary text-primary-foreground shadow-sm'
			: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
		aria-label="Toggle Fib Retrace drawing"
		title="Fibonacci Retracement"
	>
		<FibRetracementIcon class="h-4 w-4" />
	</button>

	<button
		type="button"
		onclick={() => onToggleFib?.('extension')}
		class="rounded p-1.5 transition-colors {isDrawingFib && activeFibTool === 'extension'
			? 'bg-primary text-primary-foreground shadow-sm'
			: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
		aria-label="Toggle Fib Extend drawing"
		title="Fibonacci Extension"
	>
		<FibExtensionIcon class="h-4 w-4" />
	</button>
</div>
