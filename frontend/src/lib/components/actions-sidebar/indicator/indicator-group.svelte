<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { userPreferencesService } from '$lib/api/userPreferencesService';
	import type { IndicatorConfig } from '$lib/api/indicatorsService';
	import type { UserPreferences } from '$lib/api/userPreferencesService';
	import { buildIndicatorEntry, buildToggleEntry } from '$lib/api/buildIndicatorEntry';
	import { Settings2 } from '@lucide/svelte';
	import IndicatorConfigDialog from '@/components/actions-sidebar/indicator/indicator-config-modal.svelte';
	import GroupTitle from '../group-title.svelte';
	import { INDICATOR_DEFAULTS, type IndicatorId } from '$lib/chart/indicator-defaults';

	let {
		expanded = $bindable(true),
		indicatorConfigs,
		onIndicatorToggle,
		onPreferencesLoaded,
		onIndicatorConfigChange
	} = $props<{
		expanded: boolean;
		indicatorConfigs?: Record<string, IndicatorConfig | undefined>;
		onIndicatorToggle?: (indicatorId: string, enabled: boolean) => void;
		onPreferencesLoaded?: (prefs: UserPreferences) => void;
		onIndicatorConfigChange?: (
			indicatorId: string,
			newConfig: Partial<IndicatorConfig>,
			reRender?: boolean
		) => void;
	}>();

	interface IndicatorUIProps {
		id: string;
		label: string;
		color: string;
		enabled?: boolean;
		period?: number;
		stdDev?: number;
		fast?: number;
		slow?: number;
		signal?: number;
		[key: string]: unknown;
	}

	const indicators = Object.entries(INDICATOR_DEFAULTS).map(([id, d]) => ({
		id,
		label: d.label,
		color: d.color
	}));

	let preferences = $state<UserPreferences | null>(null);

	// use expanded directly
	let isSettingsOpen = $state(false);
	let selectedIndicatorSettings = $state<IndicatorUIProps | null>(null);

	function openSettings(indicatorId: string, e: MouseEvent) {
		e.stopPropagation();
		if (!indicatorConfigs?.[indicatorId]) return;
		const indicator = indicators.find((i) => i.id === indicatorId);
		selectedIndicatorSettings = {
			id: indicatorId,
			label: indicator?.label || indicatorId,
			...indicatorConfigs[indicatorId]
		};
		isSettingsOpen = true;
	}

	async function saveSettings(id: string, newConfig: unknown) {
		if (onIndicatorConfigChange) {
			onIndicatorConfigChange(id, newConfig as Partial<IndicatorConfig>);
		}
		if (!preferences) return;

		const nc = newConfig as Partial<IndicatorConfig> & {
			period?: number;
			stdDev?: number;
			fast?: number;
			slow?: number;
			signal?: number;
		};
		const current = preferences.indicators?.[id];
		preferences.indicators = {
			...preferences.indicators,
			[id]: buildIndicatorEntry(nc, current)
		};
		try {
			await userPreferencesService.patchPreferences({ indicators: preferences.indicators });
		} catch (err) {
			console.error('Failed to save preferences:', err);
		}
	}

	/**
	 * Reset a single indicator's color and numeric settings to the canonical
	 * defaults. The enabled/disabled toggle state is deliberately preserved.
	 */
	async function resetSettings(id: string) {
		if (!preferences) return;
		const defaults = INDICATOR_DEFAULTS[id as IndicatorId];
		if (!defaults) return;

		const resetConfig: Partial<IndicatorConfig> & {
			period?: number;
			stdDev?: number;
			fast?: number;
			slow?: number;
			signal?: number;
		} = { color: defaults.color };
		if (defaults.period !== undefined) resetConfig.period = defaults.period;
		if (defaults.stdDev !== undefined) resetConfig.stdDev = defaults.stdDev;
		if (defaults.fast !== undefined) resetConfig.fast = defaults.fast;
		if (defaults.slow !== undefined) resetConfig.slow = defaults.slow;
		if (defaults.signal !== undefined) resetConfig.signal = defaults.signal;

		// Update the open modal's bound config so the inputs reflect the restored values.
		if (selectedIndicatorSettings?.id === id) {
			selectedIndicatorSettings = {
				...selectedIndicatorSettings,
				color: defaults.color,
				...(resetConfig.period !== undefined && { period: resetConfig.period }),
				...(resetConfig.stdDev !== undefined && { stdDev: resetConfig.stdDev }),
				...(resetConfig.fast !== undefined && { fast: resetConfig.fast }),
				...(resetConfig.slow !== undefined && { slow: resetConfig.slow }),
				...(resetConfig.signal !== undefined && { signal: resetConfig.signal })
			};
		}

		// enabled source of truth is the persisted preference — the page's
		// indicatorConfigs[id].enabled is stale after a sidebar toggle.
		const isEnabled =
			preferences.indicators?.[id]?.enabled ?? indicatorConfigs?.[id]?.enabled ?? false;

		onIndicatorConfigChange?.(id, resetConfig, isEnabled);

		const current = preferences.indicators?.[id];
		preferences.indicators = {
			...preferences.indicators,
			[id]: buildIndicatorEntry(resetConfig, current)
		};
		try {
			await userPreferencesService.patchPreferences({ indicators: preferences.indicators });
		} catch (err) {
			console.error('Failed to save preferences:', err);
		}
	}

	async function loadPreferences() {
		try {
			const res = await userPreferencesService.getPreferences();
			preferences = {
				...res,
				indicators: res.indicators ?? {}
			};
		} catch {
			preferences = { indicators: {} };
		}
		if (onPreferencesLoaded && preferences) {
			onPreferencesLoaded(preferences);
		}
	}

	async function toggleIndicator(indicatorId: string) {
		if (!preferences) return;

		const current = preferences.indicators?.[indicatorId];
		const newEntry = buildToggleEntry(
			current,
			indicatorConfigs?.[indicatorId]?.color || '',
			indicatorConfigs?.[indicatorId]?.enabled
		);

		const newPreferences = {
			...preferences,
			indicators: {
				...preferences.indicators,
				[indicatorId]: newEntry
			}
		};

		// Assign local state before the network await to avoid lost-update races
		preferences = newPreferences;

		try {
			await userPreferencesService.patchPreferences({ indicators: newPreferences.indicators });
			if (onIndicatorToggle) {
				onIndicatorToggle(indicatorId, newEntry.enabled);
			}
		} catch (err) {
			console.error('Failed to save preferences:', err);
		}
	}

	$effect(() => {
		loadPreferences();
	});
</script>

<Sidebar.Group>
	<GroupTitle {expanded} onToggle={() => (expanded = !expanded)}>Indicators</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			{#each indicators as indicator (indicator.id)}
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_interactive_supports_focus -->
				<div
					role="button"
					onclick={() => toggleIndicator(indicator.id)}
					class="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
				>
					<div class="flex items-center gap-2">
						<div
							class="h-2 w-2 rounded-full"
							style="background-color: {indicatorConfigs?.[indicator.id]?.color || indicator.color}"
						></div>
						<span class="cursor-default">{indicator.label}</span>
					</div>
					<div class="flex items-center gap-2">
						{#if indicator.id !== 'volume' && indicator.id !== 'avgPrice'}
							<button
								class="rounded-md p-1 text-muted-foreground hover:text-foreground"
								onclick={(e) => openSettings(indicator.id, e)}
							>
								<Settings2 class="h-4 w-4" />
							</button>
						{/if}
						<div class="pointer-events-none">
							<Checkbox
								checked={preferences?.indicators?.[indicator.id]?.enabled ??
									indicatorConfigs?.[indicator.id]?.enabled}
							/>
						</div>
					</div>
				</div>
			{/each}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>

<IndicatorConfigDialog
	bind:open={isSettingsOpen}
	bind:config={selectedIndicatorSettings}
	onSave={saveSettings}
	onReset={resetSettings}
/>
