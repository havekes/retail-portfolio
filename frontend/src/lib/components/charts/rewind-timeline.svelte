<script lang="ts">
	import type { RewindSnapshot } from '$lib/utils/finance/rewind';
	import { snapshotTimelineDomain, timeToFraction } from './rewind-timeline';
	import { formatDate } from '$lib/utils/date';

	let {
		snapshots = [],
		now = new Date(),
		position = $bindable(null)
	}: {
		snapshots?: RewindSnapshot[];
		now?: Date;
		position?: Date | null;
	} = $props();

	let domain = $derived(snapshotTimelineDomain(snapshots, now));
	let effectivePosition = $derived(position ?? now);
	let playheadPercent = $derived(
		timeToFraction(effectivePosition.getTime(), domain.first, domain.last) * 100
	);
</script>

<div
	data-testid="rewind-timeline"
	class="relative flex h-16 w-full shrink-0 flex-col justify-center border-t border-border bg-background px-4 select-none"
>
	{#if snapshots.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			No rewind snapshots yet
		</div>
	{:else}
		<div class="flex flex-col gap-1">
			<div class="relative h-7 w-full">
				<!-- Track background -->
				<div class="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted"></div>
				<!-- Highlighted scrubbable zone spanning [first, now] -->
				<div
					data-testid="rewind-timeline-zone"
					class="absolute inset-y-1.5 right-0 left-0 rounded-full bg-primary/15"
				></div>
				<!-- Snapshot point markers -->
				{#each snapshots as snapshot (snapshot.id)}
					<div
						data-testid="rewind-snapshot-point"
						class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary shadow-sm"
						style="left: {timeToFraction(
							Date.parse(snapshot.captured_at),
							domain.first,
							domain.last
						) * 100}%;"
						title={snapshot.captured_at}
					></div>
				{/each}
				<!-- Playhead -->
				<div
					data-testid="rewind-playhead"
					class="pointer-events-none absolute inset-y-0 z-10 w-0.5 -translate-x-1/2 bg-primary"
					style="left: {playheadPercent}%;"
				>
					<div
						class="absolute -top-1 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rotate-45 rounded-[1px] bg-primary"
					></div>
				</div>
			</div>
			<!-- Axis labels -->
			<div class="flex items-center justify-between text-xs text-muted-foreground">
				<span data-testid="rewind-start-label">{formatDate(snapshots[0].captured_at)}</span>
				<span data-testid="rewind-end-label" class="font-medium">Now</span>
			</div>
		</div>
	{/if}
</div>
