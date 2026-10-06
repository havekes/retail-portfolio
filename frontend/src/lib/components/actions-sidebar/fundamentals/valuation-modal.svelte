<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import Input from '@/components/ui/input/input.svelte';
	import Label from '@/components/ui/label/label.svelte';
	import Button from '@/components/ui/button/button.svelte';
	import { valuationClient, type SecurityValuationRead } from '$lib/api/valuationClient';
	import type { ModalState } from '@/utils/modal-state.svelte';

	let { modalState, onSaved } = $props<{
		modalState: ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>;
		onSaved?: (valuation: SecurityValuationRead) => void;
	}>();

	let lowerBound = $state<number | null>(null);
	let upperBound = $state<number | null>(null);
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (modalState.isOpen && modalState.data) {
			const rawLower = modalState.data.valuation?.lower_bound;
			const rawUpper = modalState.data.valuation?.upper_bound;
			lowerBound = rawLower != null ? Math.round(Number(rawLower) * 100) / 100 : null;
			upperBound = rawUpper != null ? Math.round(Number(rawUpper) * 100) / 100 : null;
			error = null;
		}
	});

	const handleSubmit = async () => {
		if (!modalState.data?.securityId) return;

		const roundedLower = lowerBound != null ? Math.round(Number(lowerBound) * 100) / 100 : null;
		const roundedUpper = upperBound != null ? Math.round(Number(upperBound) * 100) / 100 : null;

		if (roundedLower == null || roundedLower <= 0) {
			error = 'Please enter a valid lower bound (> 0)';
			return;
		}
		if (roundedUpper == null || roundedUpper <= 0) {
			error = 'Please enter a valid upper bound (> 0)';
			return;
		}
		if (roundedLower > roundedUpper) {
			error = 'Lower bound cannot be greater than upper bound';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			const res = await valuationClient.setValuation(modalState.data.securityId, {
				lower_bound: roundedLower,
				upper_bound: roundedUpper
			});
			onSaved?.(res);
			modalState.close();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to save valuation';
		} finally {
			isSubmitting = false;
		}
	};
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Set Valuation Range</Dialog.Title>
				<Dialog.Description class="py-2">
					Define the fair value lower and upper bounds for this security.
				</Dialog.Description>
			</Dialog.Header>

			{#if error}
				<div class="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
					{error}
				</div>
			{/if}

			<div class="grid gap-4 py-2">
				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-2">
						<Label for="lower-bound">Lower Bound</Label>
						<Input
							id="lower-bound"
							type="number"
							step="0.01"
							min="0"
							placeholder="e.g. 120.00"
							bind:value={lowerBound}
						/>
					</div>
					<div class="space-y-2">
						<Label for="upper-bound">Upper Bound</Label>
						<Input
							id="upper-bound"
							type="number"
							step="0.01"
							min="0"
							placeholder="e.g. 150.00"
							bind:value={upperBound}
						/>
					</div>
				</div>
			</div>

			<Dialog.Footer>
				<Button variant="outline" onclick={() => modalState.close()} disabled={isSubmitting}>
					Cancel
				</Button>
				<Button onclick={handleSubmit} disabled={isSubmitting}>
					{isSubmitting ? 'Saving...' : 'Save Valuation'}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
