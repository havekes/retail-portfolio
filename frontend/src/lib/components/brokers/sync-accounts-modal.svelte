<script lang="ts">
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogDescription
	} from '../ui/dialog/index.js';
	import { Button } from '../ui/button/index.js';
	import { Checkbox } from '../ui/checkbox/index.js';
	import { Alert, AlertDescription, AlertTitle } from '../ui/alert/index.js';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import { SyncAccountsModalState } from './sync-accounts-modal.svelte.js';
	import type { BrokerUser } from '@/types/broker/broker';
	import type { Account } from '@/types/account';
	import { getAccountTypeLabel, getInstitutionLabel } from '@/types/account';
	import type { BrokerAccount } from '@/api/types/broker';

	let {
		open = $bindable(false),
		brokerUser,
		availableAccounts,
		internalAccounts,
		onSave
	} = $props<{
		open: boolean;
		brokerUser: BrokerUser;
		availableAccounts: BrokerAccount[];
		internalAccounts: Account[];
		onSave: () => void;
	}>();

	const state = new SyncAccountsModalState(
		() => ({ open, brokerUser, availableAccounts, internalAccounts, onSave }),
		(val) => (open = val)
	);

	// Initialize checked state synchronously for the first render
	// This prevents `bind:checked` from seeing `undefined` when it has a fallback value
	state.initCheckedState();

	// Re-initialize checked state when the modal opens
	let prevOpen = false;
	$effect(() => {
		if (open && !prevOpen) {
			state.initCheckedState();
		}
		prevOpen = open;
	});
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-[600px]">
		<DialogHeader>
			<DialogTitle>{brokerUser.displayName.trim()}: select accounts to sync</DialogTitle>
			<DialogHeader>
				<DialogDescription>{getInstitutionLabel(brokerUser.institution_id)}</DialogDescription>
			</DialogHeader>
		</DialogHeader>

		{#if state.errorMessage}
			<Alert variant="destructive">
				<TriangleAlert class="h-4 w-4" />
				<AlertTitle>Error</AlertTitle>
				<AlertDescription>{state.errorMessage}</AlertDescription>
			</Alert>
		{/if}

		<div class="py-2">
			<div class="max-h-[50vh] w-full overflow-x-hidden overflow-y-auto">
				<div class="space-y-2">
					{#each availableAccounts as act (act.id)}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							class="flex cursor-pointer items-center justify-between rounded-lg bg-muted px-4 py-2 transition-colors hover:bg-muted/70"
							onclick={(e) => {
								if ((e.target as HTMLElement).closest('button')) return;
								state.handleToggle(act.id);
							}}
						>
							<div class="flex items-center space-x-4">
								<Checkbox id="sync-{act.id}" bind:checked={state.checkedState[act.id]} />
								<div class="flex-1 space-y-1">
									<div class="text-sm leading-none font-medium">
										{act.type ? getAccountTypeLabel(act.type) : 'Unknown'}
									</div>
									<div class="text-sm text-muted-foreground">
										{act.display_name}
									</div>
								</div>
							</div>
							<div class="text-sm font-medium whitespace-nowrap text-muted-foreground">
								{act.currency}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<div class="flex justify-end space-x-2">
			<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button onclick={state.handleSave} disabled={state.isSaving}>
				{#if state.isSaving}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
				{/if}
				Save
			</Button>
		</div>
	</DialogContent>
</Dialog>

<!-- Confirmation Dialog for Unsyncing -->
<Dialog bind:open={state.confirmUnsyncOpen}>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Confirm Unsync</DialogTitle>
		</DialogHeader>
		<div class="text-sm text-muted-foreground">
			<p>You are about to unsync the following accounts:</p>
			<ul class="mt-2 mb-2 list-disc pl-5">
				{#each state.accountsToUnsync as act (act.id)}
					<li>{act.name}</li>
				{/each}
			</ul>
			<p>
				This will permanently delete all associated positions and portfolio data for these accounts
				on this platform. This action cannot be undone. Are you sure you want to proceed?
			</p>
		</div>
		<div class="mt-4 flex justify-end space-x-2">
			<Button variant="outline" onclick={() => (state.confirmUnsyncOpen = false)}>Cancel</Button>
			<Button variant="destructive" disabled={state.isSaving} onclick={state.confirmSync}>
				{#if state.isSaving}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
				{/if}
				Confirm Unsync
			</Button>
		</div>
	</DialogContent>
</Dialog>
