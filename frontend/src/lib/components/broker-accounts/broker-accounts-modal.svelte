<script lang="ts">
	import * as Sheet from '$lib/components/ui/sheet';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import type { BrokerUser } from '$lib/types/broker/broker';
	import { brokerService, type BrokerAccountModel } from '$lib/services/broker/brokerService';
	import { accountService } from '$lib/services/accountService';
	import type { Account } from '$lib/types/account';

	let { brokerUser, open = $bindable(false) } = $props<{ brokerUser: BrokerUser; open: boolean }>();

	let accounts = $state<BrokerAccountModel[]>([]);
	let importedAccountIds = $state<string[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let otpRequired = $state(false);
	let otpCode = $state('');
	let selectedAccountIds = $state<string[]>([]);
	let importing = $state(false);

	async function fetchAccounts() {
		loading = true;
		error = null;
		otpRequired = false;

		try {
			// First fetch existing accounts to know what's imported
			const allAccounts = await accountService.getAccounts();
			importedAccountIds = allAccounts
				.filter((a: Account) => a.institution_id === brokerUser.institution_id && a.external_id)
				.map((a: Account) => a.external_id);

			accounts = await brokerService.getAccounts(brokerUser.institution_id, brokerUser.id);
		} catch (e: any) {
			if (e.status === 403 || e.message?.includes('OTP_REQUIRED') || e.detail === 'OTP_REQUIRED') {
				otpRequired = true;
			} else {
				error = e.message || 'Failed to fetch accounts';
			}
		} finally {
			loading = false;
		}
	}

	async function handleLogin() {
		loading = true;
		error = null;

		try {
			await brokerService.login(brokerUser.institution_id, {
				username: brokerUser.name,
				otp: otpCode
			});
			// Success, try fetching again
			await fetchAccounts();
		} catch (e: any) {
			error = e.message || 'Login failed';
			loading = false;
		}
	}

	async function importSelected() {
		if (selectedAccountIds.length === 0) return;
		importing = true;
		error = null;

		try {
			await brokerService.importAccounts(
				brokerUser.institution_id,
				brokerUser.id,
				selectedAccountIds
			);
			selectedAccountIds = [];
			open = false;
			// Ideally we would refresh the list somehow, or the parent would refresh
			// But since parent uses onMount, a full refresh or event dispatch is needed.
			// Setting a short timeout to let the user know, or just close.
		} catch (e: any) {
			error = e.message || 'Failed to import accounts';
		} finally {
			importing = false;
		}
	}

	$effect(() => {
		if (open) {
			fetchAccounts();
		} else {
			// reset state when closed
			accounts = [];
			selectedAccountIds = [];
			error = null;
			otpRequired = false;
			otpCode = '';
		}
	});

	function toggleSelection(id: string) {
		if (selectedAccountIds.includes(id)) {
			selectedAccountIds = selectedAccountIds.filter((a) => a !== id);
		} else {
			selectedAccountIds = [...selectedAccountIds, id];
		}
	}
</script>

<Sheet.Root bind:open>
	<Sheet.Content class="sm:max-w-[425px]">
		<Sheet.Header>
			<Sheet.Title>Connect Accounts: {brokerUser.name}</Sheet.Title>
			<Sheet.Description>
				Select the accounts you want to import from this connection.
			</Sheet.Description>
		</Sheet.Header>

		<div class="space-y-4 py-4">
			{#if error}
				<Alert variant="destructive">
					<AlertDescription>{error}</AlertDescription>
				</Alert>
			{/if}

			{#if loading}
				<div class="flex justify-center p-4 text-muted-foreground">Loading accounts...</div>
			{:else if otpRequired}
				<div class="space-y-4">
					<p class="text-sm text-muted-foreground">
						This connection requires 2FA authentication. Please input the code sent to your device.
					</p>
					<div class="flex space-x-2">
						<Input type="text" placeholder="OTP Code" bind:value={otpCode} />
						<Button onclick={handleLogin} disabled={!otpCode}>Submit</Button>
					</div>
				</div>
			{:else if accounts.length > 0}
				<div class="max-h-[calc(100vh-300px)] space-y-3 overflow-y-auto pr-2">
					{#each accounts as account (account.id)}
						{@const isImported = importedAccountIds.includes(account.id)}
						{@const isSelected = selectedAccountIds.includes(account.id)}

						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							class="flex items-center space-x-3 rounded-md border p-3 {isImported
								? 'bg-muted opacity-60'
								: 'cursor-pointer hover:bg-muted/50'}"
							onclick={() => !isImported && toggleSelection(account.id)}
						>
							<Checkbox checked={isImported || isSelected} disabled={isImported} />
							<div class="flex-1">
								<p class="text-sm leading-none font-medium">{account.display_name}</p>
								<p class="mt-1 text-xs text-muted-foreground">
									{account.currency} • ${account.value.toLocaleString(undefined, {
										minimumFractionDigits: 2,
										maximumFractionDigits: 2
									})}
								</p>
							</div>
							{#if isImported}
								<span class="text-xs font-semibold text-muted-foreground">Imported</span>
							{/if}
						</div>
					{/each}
				</div>
			{:else}
				<div class="p-4 text-center text-muted-foreground">No accounts found.</div>
			{/if}
		</div>

		<Sheet.Footer>
			<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button
				onclick={importSelected}
				disabled={loading || otpRequired || selectedAccountIds.length === 0 || importing}
			>
				{importing ? 'Importing...' : 'Add Accounts'}
			</Button>
		</Sheet.Footer>
	</Sheet.Content>
</Sheet.Root>
