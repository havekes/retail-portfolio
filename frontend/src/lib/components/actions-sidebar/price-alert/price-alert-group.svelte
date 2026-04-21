<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AlertListItem from './price-alert-list-item.svelte';
	import { alertsService, type PriceAlert } from '$lib/api/alertsService';
	import Plus from '@lucide/svelte/icons/plus';
	import type { SecuritySchema } from '@/api/marketService';
	import GroupTitle from '../group-title.svelte';
	import Skeleton from '@/components/ui/skeleton/skeleton.svelte';
	import PriceAlertModal from './price-alert-modal.svelte';
	import SidebarError from '../sidebar-error.svelte';
	import ConfirmationModal from '@/components/ui/confirmation-modal/confirmation-modal.svelte';
	import { ModalState } from '@/utils/modal-state.svelte';

	let {
		security,
		expanded = $bindable(true),
		alerts: externalAlerts = $bindable(undefined)
	} = $props<{
		security: SecuritySchema;
		expanded?: boolean;
		alerts?: PriceAlert[];
	}>();

	let alerts = $state<PriceAlert[]>([]);
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const createAlertModal = new ModalState<SecuritySchema>();
	const deleteConfirmationModal = new ModalState<number>();

	const handleAlertAdd = () => {
		createAlertModal.open(security);
	};

	const handleExpandToggle = () => {
		expanded = !expanded;
	};

	const handleDeleteRequest = (alertId: number) => {
		deleteConfirmationModal.open(alertId);
	};

	const handleDeleteConfirm = async () => {
		const alertId = deleteConfirmationModal.data;
		if (!security?.id || alertId === null) return;
		try {
			await alertsService.deleteAlert(security.id, alertId);
			await fetchAlerts();
		} catch (err) {
			console.error('Failed to delete alert:', err);
		}
	};

	const fetchAlerts = async () => {
		if (!security?.id) return;
		isLoading = true;
		error = null;
		try {
			alerts = await alertsService.getAlerts(security.id);
		} catch (err) {
			console.error('Failed to fetch alerts:', err);
			error = 'Failed to load alerts';
		} finally {
			isLoading = false;
		}
	};

	$effect(() => {
		if (externalAlerts) {
			alerts = externalAlerts;
		} else if (expanded && security?.id) {
			fetchAlerts();
		}
	});
</script>

<PriceAlertModal modalState={createAlertModal} onCreated={fetchAlerts} />

<ConfirmationModal
	bind:open={deleteConfirmationModal.isOpen}
	title="Delete Price Alert"
	description="Are you sure you want to delete this price alert?"
	onconfirm={handleDeleteConfirm}
/>

<Sidebar.Group>
	<GroupTitle {expanded} onToggle={handleExpandToggle} actionIcon={Plus} onAction={handleAlertAdd}>
		Price Alerts
	</GroupTitle>

	{#if expanded}
		<Sidebar.GroupContent>
			{#if isLoading}
				<div class="space-y-2 py-2">
					<Skeleton class="h-16 w-full rounded-md bg-background" />
					<Skeleton class="h-16 w-full rounded-md bg-background" />
				</div>
			{:else if error}
				<div class="py-2">
					<SidebarError message={error} onretry={fetchAlerts} />
				</div>
			{:else if alerts.length === 0}
				<div class="p-2 text-xs">No alerts yet</div>
			{:else}
				<div class="space-y-1 py-2">
					{#each alerts as alert (alert.id)}
						<AlertListItem {alert} ondelete={() => handleDeleteRequest(alert.id)} />
					{/each}
				</div>
			{/if}
		</Sidebar.GroupContent>
	{/if}
</Sidebar.Group>
