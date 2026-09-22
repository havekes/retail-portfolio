<script lang="ts">
	import { notesService } from '$lib/api/notesService';
	import { ApiError } from '$lib/api/apiClient';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import SidebarError from '../sidebar-error.svelte';

	let {
		securityId,
		pollIntervalMs = 2000,
		maxPollAttempts = 30
	} = $props<{
		securityId: string;
		/** Gap between regeneration polls; overridable so tests don't need fake timers. */
		pollIntervalMs?: number;
		/** How many polls to run before giving up and showing the last persisted value. */
		maxPollAttempts?: number;
	}>();

	let summary = $state<string | null>(null);
	let generatedAt = $state<string | null>(null);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let regenerating = $state(false);

	// Every load/refresh takes a token; a newer request (or an unmount) makes older
	// in-flight requests and scheduled polls no-ops so responses can never race.
	let requestToken = 0;
	let pollTimer: ReturnType<typeof setTimeout> | null = null;
	let pollResolve: (() => void) | null = null;

	function cancelPoll() {
		if (pollTimer !== null) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
		const resolve = pollResolve;
		pollResolve = null;
		// The waiting loop re-checks its token and exits when it is no longer current.
		resolve?.();
	}

	function waitForNextPoll(): Promise<void> {
		return new Promise((resolve) => {
			pollResolve = resolve;
			pollTimer = setTimeout(() => {
				pollTimer = null;
				pollResolve = null;
				resolve();
			}, pollIntervalMs);
		});
	}

	function describeError(err: unknown): string {
		// Only the API's own message is user-facing; anything else (e.g. a network
		// TypeError) is wrapped in the same generic copy `fetchNotes` falls back to.
		return err instanceof ApiError ? err.message : 'Failed to load summary';
	}

	async function fetchSummary(token: number, id: string): Promise<'ok' | 'error' | 'stale'> {
		try {
			const result = await notesService.getLatestSummary(id);
			if (token !== requestToken) return 'stale';
			summary = result.summary;
			generatedAt = result.generated_at;
			error = null;
			return 'ok';
		} catch (err) {
			if (token !== requestToken) return 'stale';
			error = describeError(err);
			return 'error';
		}
	}

	async function load(id: string) {
		const token = ++requestToken;
		cancelPoll();
		isLoading = true;
		error = null;
		regenerating = false;
		await fetchSummary(token, id);
		if (token !== requestToken) return;
		isLoading = false;
	}

	// Called by the group after every note mutation. Regeneration is asynchronous
	// (huey), so the first GET still returns the previously persisted summary: poll
	// until `generated_at` moves, then adopt the fresh text.
	export async function refresh() {
		const token = ++requestToken;
		cancelPoll();
		// A refresh supersedes an in-flight initial load (same token guard), so make
		// sure the skeleton can't get stuck on for a load that will never report back.
		isLoading = false;
		regenerating = true;
		error = null;
		const baseline = generatedAt;

		for (let attempt = 0; attempt < maxPollAttempts; attempt++) {
			if (attempt > 0) {
				await waitForNextPoll();
				if (token !== requestToken) return;
			}

			const outcome = await fetchSummary(token, securityId);
			if (outcome === 'stale') return;
			if (outcome === 'error') {
				regenerating = false;
				return;
			}
			if (generatedAt !== baseline || (baseline === null && summary !== null)) {
				regenerating = false;
				return;
			}
		}

		// Regeneration never landed inside the polling window: keep showing the last
		// persisted value (or the pending state) instead of spinning indefinitely.
		regenerating = false;
	}

	async function retry() {
		const token = ++requestToken;
		cancelPoll();
		// A retry is a single GET; a null result simply falls back to the pending state.
		await fetchSummary(token, securityId);
	}

	$effect(() => {
		// Re-runs when the security changes; the cleanup stops any scheduled poll so
		// it can neither bleed across securities nor fire after unmount.
		void load(securityId);
		return () => {
			requestToken++;
			cancelPoll();
		};
	});
</script>

<div class="mb-2 space-y-1.5">
	<div
		class="flex items-center gap-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
	>
		<Sparkles class="h-3 w-3" />
		AI summary
	</div>

	{#if error}
		<SidebarError message={error} onretry={retry} />
	{:else if summary}
		<div>
			<p class="rounded-md bg-accent/50 p-3 text-xs leading-relaxed whitespace-pre-wrap">
				{summary}
			</p>
			{#if regenerating}
				<p class="mt-1 text-[10px] text-muted-foreground">Updating summary…</p>
			{/if}
		</div>
	{:else if isLoading}
		<Skeleton class="h-12 w-full" />
	{:else}
		<p class="rounded-md bg-accent/50 p-3 text-xs text-muted-foreground">
			{regenerating ? 'Generating summary…' : 'Summary pending…'}
		</p>
	{/if}
</div>
