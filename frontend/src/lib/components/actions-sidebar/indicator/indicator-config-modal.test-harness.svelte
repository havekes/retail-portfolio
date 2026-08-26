<script lang="ts">
	import IndicatorConfigModal from './indicator-config-modal.svelte';
	import type { IndicatorSettings } from '$lib/api/indicatorsService';

	let {
		config = $bindable(null),
		onSave,
		onReset
	}: {
		config: IndicatorSettings | null;
		onSave: (id: string, updatedConfig: IndicatorSettings) => void;
		onReset: (id: string) => void;
	} = $props();

	// Mirror the real parent (indicator-group.svelte) which passes a $state-proxied
	// config, so object mutations inside the modal propagate reactively.
	let open = $state(true);
	let reactiveConfig = $state(config);
</script>

<IndicatorConfigModal bind:open bind:config={reactiveConfig} {onSave} {onReset} />
