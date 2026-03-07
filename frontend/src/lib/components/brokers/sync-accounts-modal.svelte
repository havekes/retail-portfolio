<script lang="ts">
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogDescription
	} from '../ui/dialog';
	import { Button } from '../ui/button';
	import { Checkbox } from '../ui/checkbox';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import type { BrokerUser } from '@/types/broker/broker';
	import type { Account } from '@/types/account';
	import { getAccountTypeLabel, getInstitutionLabel } from '@/types/account';
	import { accountService } from '@/services/accountService';
	import { brokerService } from '@/services/broker/brokerService';

	let {
		open = $bindable(false),
		brokerUser,
		availableAccounts,
		internalAccounts,
		onSave
	} = $props<{
		open: boolean;
		brokerUser: BrokerUser;
		availableAccounts: any[];
		internalAccounts: Account[];
		onSave: () => void;
	}>();

	let checkedState = $state<Record<string, boolean>>(
		Object.fromEntries(
			availableAccounts.map((acc: any) => [
				acc.id,
				internalAccounts.some((iAcc: Account) => iAcc.external_id === acc.id)
			])
		)
	);
	let isSaving = $state(false);
	let confirmUnsyncOpen = $state(false);
	let accountsToUnsync = $state<Account[]>([]);

	// Initialize checked state when the modal opens
	$effect(() => {
		if (open) {
			const newCheckedState: Record<string, boolean> = {};
			availableAccounts.forEach((acc: any) => {
				const isCurrentlySynced = internalAccounts.some(
					(iAcc: Account) => iAcc.external_id === acc.id
				);
				newCheckedState[acc.id] = isCurrentlySynced;
			});
			checkedState = newCheckedState;
		}
	});

	async function handleSave() {
		const newlyCheckedExternalIds = Object.entries(checkedState)
			.filter(([_, isChecked]) => isChecked)
			.map(([id]) => id);

		// Find accounts that were unchecked but are currently synced
		accountsToUnsync = internalAccounts.filter(
			(acc: Account) => checkedState[acc.external_id] === false
		);

		if (accountsToUnsync.length > 0) {
			confirmUnsyncOpen = true;
		} else {
			await performSync(newlyCheckedExternalIds);
		}
	}

	async function performSync(checkedExternalIds: string[]) {
		isSaving = true;
		try {
			// Import newly checked accounts
			if (checkedExternalIds.length > 0) {
				await brokerService.importAccounts(
					brokerUser.institution_id,
					brokerUser.id,
					checkedExternalIds
				);
			}

			// Delete unchecked accounts
			for (const acc of accountsToUnsync) {
				await accountService.deleteAccount(acc.id);
			}

			open = false;
			confirmUnsyncOpen = false;
			onSave();
		} catch (error) {
			console.error('Failed to sync accounts:', error);
		} finally {
			isSaving = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-[600px]">
		<DialogHeader>
			<DialogTitle>{brokerUser.name.trim()}: select accounts to sync</DialogTitle>
			<DialogDescription>{getInstitutionLabel(brokerUser.institution_id)}</DialogDescription>
		</DialogHeader>

		<div class="py-4">
			<div class="max-h-[60vh] w-full overflow-x-hidden overflow-y-auto">
				<div class="space-y-4 pr-2">
					{#each availableAccounts as act}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							class="flex cursor-pointer items-center justify-between rounded-lg bg-muted p-4 transition-colors hover:bg-muted/80"
							onclick={(e) => {
								if ((e.target as HTMLElement).closest('button')) return;
								checkedState[act.id] = !checkedState[act.id];
							}}
						>
							<div class="flex items-center space-x-4">
								<Checkbox id="sync-{act.id}" bind:checked={checkedState[act.id]} />
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
			<Button onclick={handleSave} disabled={isSaving}>
				{#if isSaving}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
				{/if}
				Save
			</Button>
		</div>
	</DialogContent>
</Dialog>

<!-- Confirmation Dialog for Unsyncing -->
<Dialog bind:open={confirmUnsyncOpen}>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Confirm Unsync</DialogTitle>
		</DialogHeader>
		<div class="text-sm text-muted-foreground">
			<p>You are about to unsync the following accounts:</p>
			<ul class="mt-2 mb-2 list-disc pl-5">
				{#each accountsToUnsync as act}
					<li>{act.name}</li>
				{/each}
			</ul>
			<p>
				This will permanently delete all associated positions and portfolio data for these accounts
				on this platform. This action cannot be undone. Are you sure you want to proceed?
			</p>
		</div>
		<div class="mt-4 flex justify-end space-x-2">
			<Button variant="outline" onclick={() => (confirmUnsyncOpen = false)}>Cancel</Button>
			<Button
				variant="destructive"
				disabled={isSaving}
				onclick={() => {
					const newlyCheckedExternalIds = Object.entries(checkedState)
						.filter(([_, isChecked]) => isChecked)
						.map(([id]) => id);
					performSync(newlyCheckedExternalIds);
				}}
			>
				{#if isSaving}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
				{/if}
				Confirm Unsync
			</Button>
		</div>
	</DialogContent>
</Dialog>
