<script lang="ts">
	import type { WaveDegree } from '$lib/utils/finance/elliott-wave';
	import type { FibToolType } from '$lib/utils/finance/fibonacci';
	import WaveIcon from '$lib/components/icons/wave-icon.svelte';
	import FibRetracementIcon from '$lib/components/icons/fib-retracement-icon.svelte';
	import FibExtensionIcon from '$lib/components/icons/fib-extension-icon.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';

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

<Tooltip.Provider>
	<div class="flex w-10 shrink-0 flex-col items-center gap-1 border-r bg-sidebar/50 p-1.5">
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
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content side="right">
					<p>Elliott Wave</p>
				</Tooltip.Content>
			</Tooltip.Root>
			<DropdownMenu.Content side="right" align="start" class="z-50 min-w-44">
				<DropdownMenu.Label>Degree</DropdownMenu.Label>
				<DropdownMenu.Separator />
				<DropdownMenu.Item
					onSelect={() => onSelectWaveDegree?.('cycle')}
					onclick={() => onSelectWaveDegree?.('cycle')}
					class={activeWaveDegree === 'cycle' ? 'font-medium' : ''}
				>
					Cycle (I, II, III)
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => onSelectWaveDegree?.('primary')}
					onclick={() => onSelectWaveDegree?.('primary')}
					class={activeWaveDegree === 'primary' ? 'font-medium' : ''}
				>
					Primary (①, ②, ③)
				</DropdownMenu.Item>
				<DropdownMenu.Item
					onSelect={() => onSelectWaveDegree?.('intermediate')}
					onclick={() => onSelectWaveDegree?.('intermediate')}
					class={activeWaveDegree === 'intermediate' ? 'font-medium' : ''}
				>
					Intermediate ((1), (2), (3))
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>

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
