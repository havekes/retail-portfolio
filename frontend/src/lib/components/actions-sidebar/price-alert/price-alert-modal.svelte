<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as ChoiceBox from '$lib/components/ui/choicebox/index.js';
	import TrendingUp from '@lucide/svelte/icons/trending-up';
	import TrendingDown from '@lucide/svelte/icons/trending-down';
	import Input from '@/components/ui/input/input.svelte';
	import Label from '@/components/ui/label/label.svelte';
	import Button from '@/components/ui/button/button.svelte';
	import { alertsService, type PriceAlertCreateRequest } from '$lib/api/alertsService';
	import { type SecuritySchema } from '$lib/api/marketService';
	import type { ModalState } from '@/utils/modal-state.svelte';

	let { modalState, onCreated } = $props<{
		modalState: ModalState<SecuritySchema>;
		onCreated?: () => void;
	}>();

	let targetPrice = $state<number | null>(null);
	let condition = $state<'above' | 'below'>('below');
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);

	// Reset state when modal closes
	$effect(() => {
		if (!modalState.isOpen) {
			targetPrice = null;
			condition = 'below';
			error = null;
		}
	});

	const handleSubmit = async () => {
		if (!modalState.data || !targetPrice || targetPrice <= 0) {
			error = 'Please enter a valid target price';
			return;
		}

		isSubmitting = true;
		error = null;

		try {
			const request: PriceAlertCreateRequest = {
				target_price: targetPrice,
				condition: condition
			};
			await alertsService.createAlert(modalState.data.id, request);
			if (onCreated) onCreated();
			modalState.close();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to create alert';
		} finally {
			isSubmitting = false;
		}
	};

	const handleKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleSubmit();
		}
	};
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content onkeydown={handleKeyDown}>
			<Dialog.Header>
				<Dialog.Title>Create price alert</Dialog.Title>
				<Dialog.Description class="py-2">
					You'll be notified when the price meets your condition.
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4">
				{#if error}
					<div
						class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
					>
						{error}
					</div>
				{/if}

				<div class="space-y-4">
					<Label for="target-price">Target price</Label>
					<Input
						id="target-price"
						type="number"
						step="0.01"
						min="0"
						bind:value={targetPrice}
						placeholder="Enter target price"
					/>
				</div>

				<div class="space-y-4">
					<Label>Condition</Label>
					<ChoiceBox.Root bind:value={condition}>
						<ChoiceBox.Item value="above">
							<div class="flex flex-col gap-2">
								<div class="flex items-center gap-2">
									<TrendingUp class="h-4 w-4 text-green-500" />
									<ChoiceBox.Title>Price goes above</ChoiceBox.Title>
								</div>
								<ChoiceBox.Description>
									Notify when price reaches or exceeds target
								</ChoiceBox.Description>
							</div>
						</ChoiceBox.Item>
						<ChoiceBox.Item value="below">
							<div class="flex flex-1 flex-col gap-2">
								<div class="flex items-center gap-2">
									<TrendingDown class="h-4 w-4 text-red-500" />
									<ChoiceBox.Title>Price goes below</ChoiceBox.Title>
								</div>
								<ChoiceBox.Description>
									Notify when price reaches or drops below target
								</ChoiceBox.Description>
							</div>
						</ChoiceBox.Item>
					</ChoiceBox.Root>
				</div>
			</div>

			<Dialog.Footer>
				<Button onclick={() => modalState.close()} variant="outline">Cancel</Button>
				<Button onclick={handleSubmit} disabled={isSubmitting}>
					{isSubmitting ? 'Creating...' : 'Create alert'}
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
