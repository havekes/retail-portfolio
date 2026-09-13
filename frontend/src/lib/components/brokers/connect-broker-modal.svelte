<script lang="ts">
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogDescription
	} from '$lib/components/ui/dialog';
	import { ConnectBrokerModalState } from './connect-broker-modal.svelte.js';
	import type { BackendInstitution } from '@/types/broker/broker';
	import { onMount } from 'svelte';
	import BrokerLoginModal from './broker-login-modal.svelte';
	import ImportAccountCsvModal from '../accounts/import-account-csv-modal.svelte';
	import { Button } from '$lib/components/ui/button';
	import { RadioCards } from '$lib/components/ui/radio-cards';
	import { Alert, AlertDescription, AlertTitle } from '$lib/components/ui/alert';
	import { AlertCircle } from '@lucide/svelte';

	let { open = $bindable(false), onSuccess } = $props<{
		open: boolean;
		onSuccess: () => void;
	}>();

	const state = new ConnectBrokerModalState((val) => (open = val));

	$effect(() => {
		if (open) {
			state.reset();
		}
	});

	onMount(() => {
		state.loadInstitutions();
	});
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-[425px]">
		<DialogHeader>
			<DialogTitle>Connect broker</DialogTitle>
			<DialogDescription>Select your broker to sync your accounts.</DialogDescription>
		</DialogHeader>

		<div class="max-h-[60vh] overflow-y-auto px-1 py-4">
			{#if state.errorMessage}
				<div class="mb-4">
					<Alert variant="destructive">
						<AlertCircle class="h-4 w-4" />
						<AlertTitle>Error</AlertTitle>
						<AlertDescription>
							{state.errorMessage}
						</AlertDescription>
					</Alert>
				</div>
			{/if}

			<RadioCards
				items={state.institutions}
				onSelect={state.handleSelect}
				class="grid-cols-2"
				itemClass="hover:bg-accent hover:text-accent-foreground"
			>
				{#snippet children(inst: BackendInstitution)}
					<div
						class="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground"
					>
						Logo
					</div>
					<span class="text-center text-sm font-medium">{inst.name}</span>
				{/snippet}
			</RadioCards>

			<div class="mt-4 border-t pt-4 text-center">
				<p class="mb-2 text-xs text-muted-foreground">Or import from a CSV file export</p>
				<Button variant="outline" class="w-full" onclick={state.openCsvImport}>
					Import accounts from CSV
				</Button>
			</div>
		</div>
	</DialogContent>
</Dialog>

<BrokerLoginModal
	bind:open={state.isLoginModalOpen}
	institution={state.selectedInstitution}
	{onSuccess}
/>

<ImportAccountCsvModal bind:open={state.isCsvImportModalOpen} {onSuccess} />
