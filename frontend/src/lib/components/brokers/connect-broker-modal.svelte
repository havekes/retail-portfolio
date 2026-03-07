<script lang="ts">
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogDescription
	} from '$lib/components/ui/dialog';
	import { brokerService } from '@/services/broker/brokerService';
	import type { BackendInstitution } from '@/types/broker/broker';
	import { onMount } from 'svelte';
	import BrokerLoginModal from './broker-login-modal.svelte';
	import { RadioCards } from '$lib/components/ui/radio-cards';

	export let open = false;
	export let onSuccess: () => void;

	let institutions: BackendInstitution[] = [];
	let selectedInstitution: BackendInstitution | null = null;
	let isLoginModalOpen = false;

	$: if (open) {
		selectedInstitution = null;
	}

	onMount(async () => {
		try {
			institutions = await brokerService.getInstitutions();
		} catch (e) {
			console.error('Failed to load institutions', e);
		}
	});
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-[425px]">
		<DialogHeader>
			<DialogTitle>Connect broker</DialogTitle>
			<DialogDescription>Select your broker to sync your accounts.</DialogDescription>
		</DialogHeader>

		<div class="max-h-[60vh] overflow-y-auto px-1 py-4">
			<RadioCards
				items={institutions}
				onSelect={(id: string) => {
					const inst = institutions.find((i) => i.id === id);
					if (inst) {
						selectedInstitution = inst;
						open = false;
						isLoginModalOpen = true;
					}
				}}
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
		</div>
	</DialogContent>
</Dialog>

<BrokerLoginModal bind:open={isLoginModalOpen} institution={selectedInstitution} {onSuccess} />
