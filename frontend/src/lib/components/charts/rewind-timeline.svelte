<script lang="ts">
	import type { RewindSnapshot } from '$lib/utils/finance/rewind';
	import { snapshotTimelineDomain, timeToFraction, fractionToTime } from './rewind-timeline';
	import { formatDate } from '$lib/utils/date';

	let {
		snapshots = [],
		now = new Date(),
		position = $bindable(null),
		onScrub
	}: {
		snapshots?: RewindSnapshot[];
		now?: Date;
		position?: Date | null;
		onScrub?: (position: Date | null) => void;
	} = $props();

	let domain = $derived(snapshotTimelineDomain(snapshots, now));
	let effectivePosition = $derived(position ?? now);
	let playheadPercent = $derived(
		timeToFraction(effectivePosition.getTime(), domain.first, domain.last) * 100
	);

	let trackEl: HTMLDivElement | null = $state(null);
	let isDragging = $state(false);

	function updatePositionFromPointer(clientX: number) {
		if (!trackEl) return;
		const rect = trackEl.getBoundingClientRect();
		const width = rect.width > 0 ? rect.width : 1;
		const fraction = Math.max(0, Math.min(1, (clientX - rect.left) / width));
		let newPos: Date | null = null;
		if (fraction < 0.995) {
			newPos = fractionToTime(fraction, domain.first, domain.last);
		}
		position = newPos;
		onScrub?.(newPos);
	}

	function handlePointerDown(e: PointerEvent) {
		if (snapshots.length === 0) return;
		isDragging = true;
		if (typeof (e.currentTarget as HTMLElement).setPointerCapture === 'function') {
			try {
				(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
			} catch {
				// ignore
			}
		}
		updatePositionFromPointer(e.clientX);
	}

	function handlePointerMove(e: PointerEvent) {
		if (!isDragging) return;
		updatePositionFromPointer(e.clientX);
	}

	function handlePointerUp(e: PointerEvent) {
		if (!isDragging) return;
		isDragging = false;
		if (typeof (e.currentTarget as HTMLElement).releasePointerCapture === 'function') {
			try {
				(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
			} catch {
				// ignore
			}
		}
	}

	function handleWindowPointerUp() {
		if (isDragging) {
			isDragging = false;
		}
	}

	function selectSnapshot(snapshot: RewindSnapshot) {
		const snapDate = new Date(snapshot.captured_at);
		position = snapDate;
		onScrub?.(snapDate);
	}

	function resetToNow() {
		position = null;
		onScrub?.(null);
	}
</script>

<svelte:window onpointerup={handleWindowPointerUp} onpointercancel={handleWindowPointerUp} />

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
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					bind:this={trackEl}
					data-testid="rewind-timeline-zone"
					class="absolute inset-y-1.5 right-0 left-0 cursor-pointer rounded-full bg-primary/15"
					onpointerdown={handlePointerDown}
					onpointermove={handlePointerMove}
					onpointerup={handlePointerUp}
				></div>
				<!-- Snapshot point markers -->
				{#each snapshots as snapshot (snapshot.id)}
					<button
						type="button"
						data-testid="rewind-snapshot-point"
						class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary shadow-sm transition-transform hover:scale-125 focus:outline-hidden"
						style="left: {timeToFraction(
							Date.parse(snapshot.captured_at),
							domain.first,
							domain.last
						) * 100}%;"
						title={snapshot.captured_at}
						aria-label="Snapshot at {snapshot.captured_at}"
						onclick={(e) => {
							e.stopPropagation();
							selectSnapshot(snapshot);
						}}
						onpointerdown={(e) => {
							e.stopPropagation();
						}}
					></button>
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
				{#if position !== null}
					<button
						type="button"
						data-testid="rewind-back-to-now"
						onclick={resetToNow}
						class="rounded px-2 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
					>
						Back to now
					</button>
				{/if}
				<button
					type="button"
					data-testid="rewind-end-label"
					onclick={resetToNow}
					class="font-medium transition-colors hover:text-foreground {position === null
						? 'text-primary'
						: ''}"
				>
					Now
				</button>
			</div>
		</div>
	{/if}
</div>
