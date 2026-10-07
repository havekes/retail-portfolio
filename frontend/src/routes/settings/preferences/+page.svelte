<script lang="ts">
	import AppHeader from '$lib/components/layout/app-header.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import {
		SUPPORTED_DISPLAY_CURRENCIES,
		userPreferencesService,
		type DisplayCurrency
	} from '$lib/api/userPreferencesService';

	let { data } = $props();

	let displayCurrency = $state<DisplayCurrency>(
		(data.display_currency as DisplayCurrency) ?? 'CAD'
	);
	let error = $state<string | null>(null);
	let isSaving = $state(false);

	async function handleChange(event: Event) {
		const select = event.currentTarget as HTMLSelectElement;
		const previous = displayCurrency;
		const next = select.value as DisplayCurrency;
		if (next === previous) {
			return;
		}

		displayCurrency = next;
		error = null;
		isSaving = true;
		try {
			const updated = await userPreferencesService.patchPreferences({
				display_currency: next
			});
			if (updated.display_currency) {
				displayCurrency = updated.display_currency as DisplayCurrency;
			}
		} catch (err) {
			// Revert the select on failure so the UI reflects the stored value.
			displayCurrency = previous;
			select.value = previous;
			error = err instanceof Error ? err.message : 'Failed to update display currency.';
		} finally {
			isSaving = false;
		}
	}
</script>

<svelte:head>
	<title>Preferences</title>
</svelte:head>

<div class="flex h-full flex-col">
	<AppHeader title="Preferences" subtitle="Control how your portfolio is displayed" />
	<div class="flex-1 overflow-y-auto">
		<div class="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
			{#if error}
				<Alert.Root variant="destructive">
					<Alert.Description>{error}</Alert.Description>
				</Alert.Root>
			{/if}

			<Card.Root>
				<Card.Header>
					<Card.Title>Display currency</Card.Title>
					<Card.Description>
						The currency used for totals and values in cross-account views.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="flex flex-col gap-2">
						<Label for="display-currency">Display currency</Label>
						<select
							id="display-currency"
							class="h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
							value={displayCurrency}
							onchange={handleChange}
						>
							{#each SUPPORTED_DISPLAY_CURRENCIES as currency (currency)}
								<option value={currency}>{currency}</option>
							{/each}
						</select>
						{#if isSaving}
							<p class="text-sm text-muted-foreground">Saving…</p>
						{/if}
					</div>
				</Card.Content>
			</Card.Root>
		</div>
	</div>
</div>
