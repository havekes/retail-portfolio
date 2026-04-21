<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { indicatorsService } from '$lib/api/indicatorsService';
	import type { IndicatorConfig, IndicatorPreferences } from '$lib/api/indicatorsService';
	import { Settings2 } from '@lucide/svelte';
	import IndicatorConfigDialog from '@/components/actions-sidebar/indicator/indicator-config-modal.svelte';
	import GroupTitle from '../group-title.svelte';

	let {
		expanded = $bindable(true),
		securityId,
		indicatorConfigs,
		onIndicatorToggle,
		onPreferencesLoaded,
		onIndicatorConfigChange
	} = $props<{
		expanded: boolean;
		securityId: string;
		indicatorConfigs?: Record<string, any>;
		onIndicatorToggle?: (indicatorId: string, enabled: boolean) => void;
		onPreferencesLoaded?: (prefs: IndicatorPreferences) => void;
		onIndicatorConfigChange?: (indicatorId: string, newConfig: IndicatorConfig) => void;
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
		[key: string]: any;
	}

	const indicators = [
		{ id: 'volume', label: 'Volume', color: '#64748b' },
		{ id: 'avgPrice', label: 'Avg Price', color: '#f59e0b' },
		{ id: 'ma50', label: '50 Day MA', color: '#3b82f6' },
		{ id: 'ma200', label: '200 Day MA', color: '#8b5cf6' },
		{ id: 'ma50w', label: '50 Week MA', color: '#10b981' },
		{ id: 'ma200w', label: '200 Week MA', color: '#f59e0b' },
		{ id: 'bb', label: 'Bollinger Bands', color: '#8b5cf6' },
		{ id: 'macd', label: 'MACD', color: '#ef4444' },
		{ id: 'rsi', label: 'RSI', color: '#06b6d4' },
		{ id: 'obv', label: 'OBV', color: '#f59e0b' }
	];

	let preferences = $state<IndicatorPreferences | null>(null);

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

	function saveSettings(id: string, newConfig: any) {
		if (onIndicatorConfigChange) {
			onIndicatorConfigChange(id, newConfig as IndicatorConfig);
		}
	}

	async function loadPreferences() {
		try {
			const res = await indicatorsService.getPreferences(securityId);
			preferences = res || {
				security_id: securityId,
				user_id: '',
				indicators: {}
			};
			if (!preferences.indicators) {
				preferences.indicators = {};
			}
		} catch {
			preferences = {
				security_id: securityId,
				user_id: '',
				indicators: {}
			};
		}
		if (onPreferencesLoaded && preferences) {
			onPreferencesLoaded(preferences);
		}
	}

	async function toggleIndicator(indicatorId: string) {
		if (!preferences) return;

		const current = preferences.indicators[indicatorId];
		const currentEnabled = current?.enabled ?? indicatorConfigs?.[indicatorId]?.enabled;
		const newEnabled = !currentEnabled;

		const newPreferences = {
			...preferences,
			indicators: {
				...preferences.indicators,
				[indicatorId]: {
					enabled: newEnabled,
					color: current?.color || '',
					settings: current?.settings || {}
				}
			}
		};

		try {
			// await indicatorsService.savePreferences(securityId, newPreferences);
			preferences = newPreferences;
			if (onIndicatorToggle) {
				onIndicatorToggle(indicatorId, newEnabled);
			}
		} catch (err) {
			console.error('Failed to save preferences:', err);
		}
	}

	$effect(() => {
		if (securityId) {
			loadPreferences();
		}
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
								checked={preferences?.indicators[indicator.id]?.enabled ??
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
/>
