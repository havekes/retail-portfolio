<script lang="ts">
	import { untrack } from 'svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import GroupTitle from '../group-title.svelte';
	import Skeleton from '@/components/ui/skeleton/skeleton.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import Button from '@/components/ui/button/button.svelte';
	import Checkbox from '@/components/ui/checkbox/checkbox.svelte';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Plus from '@lucide/svelte/icons/plus';
	import { valuationClient, type SecurityValuationRead } from '$lib/api/valuationClient';
	import { userPreferencesService } from '$lib/api/userPreferencesService';
	import ValuationModal from './valuation-modal.svelte';
	import { ModalState } from '$lib/utils/modal-state.svelte';

	let {
		securityId,
		currency = 'USD',
		valuation = $bindable<SecurityValuationRead | null>(null),
		showOverlay = $bindable(true),
		expanded = $bindable(true)
	} = $props<{
		securityId?: string;
		currency?: string;
		valuation?: SecurityValuationRead | null;
		showOverlay?: boolean;
		expanded?: boolean;
	}>();

	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const valuationModalState = new ModalState<{
		securityId: string;
		valuation?: SecurityValuationRead | null;
	}>();

	const handleOpenModal = () => {
		if (!securityId) return;
		valuationModalState.open({
			securityId,
			valuation
		});
	};

	const fetchValuation = async () => {
		if (!securityId) return;
		isLoading = true;
		error = null;
		try {
			valuation = await valuationClient.getValuation(securityId);
		} catch (err) {
			console.error('Failed to fetch valuation:', err);
			error = 'Failed to load valuation';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (expanded && securityId) {
			untrack(() => {
				fetchValuation();
			});
		}
	});

	const formatCurrency = (val: number) => {
		return new Intl.NumberFormat('en-US', {
			style: 'currency',
			currency
		}).format(val);
	};

	const handleToggleOverlay = async (checked: boolean | 'indeterminate') => {
		const val = checked === true;
		showOverlay = val;
		try {
			await userPreferencesService.patchPreferences({ show_valuation_band: val });
		} catch (err) {
			console.error('Failed to save valuation band preference:', err);
		}
	};
</script>

<ValuationModal
	modalState={valuationModalState}
	onSaved={(saved) => {
		valuation = saved;
	}}
/>

<Sidebar.Group>
	<GroupTitle
		{expanded}
		onToggle={() => (expanded = !expanded)}
		actionIcon={valuation ? Pencil : Plus}
		actionTitle={valuation ? 'Edit valuation' : 'Add valuation'}
		onAction={handleOpenModal}
	>
		Fundamentals
	</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			{#if isLoading}
				<div class="space-y-2 py-2">
					<Skeleton class="h-8 w-full rounded-md bg-background" />
				</div>
			{:else if error}
				<div class="py-2">
					<SidebarError message={error} onretry={fetchValuation} />
				</div>
			{:else if !valuation}
				<div class="space-y-2 p-2 text-sm">
					<div class="text-muted-foreground">Fair value range not set.</div>
					<Button variant="outline" size="sm" class="w-full text-xs" onclick={handleOpenModal}>
						Set Valuation Range
					</Button>
				</div>
			{:else}
				<div class="space-y-2.5 py-2 text-sm">
					<div class="rounded-md bg-muted/40 p-2.5">
						<div class="flex items-center justify-between">
							<span class="text-xs text-muted-foreground">Fair Value Range</span>
							<button
								type="button"
								onclick={handleOpenModal}
								class="text-xs text-primary hover:underline"
							>
								Edit
							</button>
						</div>
						<div class="mt-1 flex items-center justify-between">
							<span class="font-semibold text-foreground">
								{formatCurrency(valuation.lower_bound)} – {formatCurrency(valuation.upper_bound)}
							</span>
							<Checkbox
								id="show-valuation-overlay"
								checked={showOverlay}
								onCheckedChange={handleToggleOverlay}
								aria-label="Show on chart"
								title="Show on chart"
							/>
						</div>
					</div>
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>
