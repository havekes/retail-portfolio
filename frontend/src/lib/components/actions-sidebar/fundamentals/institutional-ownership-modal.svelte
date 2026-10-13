<script module lang="ts">
	import type { InstitutionalOwnershipResponse } from '$lib/api/marketService';

	export interface InstitutionalOwnershipModalData {
		securityId?: string;
		symbol?: string;
		data?: InstitutionalOwnershipResponse | null;
	}

	export function formatOwnershipPercent(val: number | null | undefined): string {
		if (val == null || isNaN(Number(val))) return 'N/A';
		return `${Number(val).toFixed(2)}%`;
	}

	export function formatInvestorCount(val: number | null | undefined): string {
		if (val == null || isNaN(Number(val))) return 'N/A';
		return new Intl.NumberFormat('en-US').format(Number(val));
	}

	export function formatTotalInvested(val: number | string | null | undefined): string {
		if (val == null) return 'N/A';
		const num = Number(val);
		if (isNaN(num)) return 'N/A';
		if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
		if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
		if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
		return new Intl.NumberFormat('en-US', {
			style: 'currency',
			currency: 'USD',
			maximumFractionDigits: 0
		}).format(num);
	}
</script>

<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import Button from '@/components/ui/button/button.svelte';
	import type { ModalState } from '@/utils/modal-state.svelte';
	import { formatDate } from '$lib/utils/date';

	let { modalState } = $props<{
		modalState: ModalState<InstitutionalOwnershipModalData>;
	}>();

	let ownership = $derived(modalState.data?.data);
	let ticker = $derived(modalState.data?.symbol || ownership?.symbol || 'Security');
	let history = $derived(ownership?.history ?? []);
</script>

<Dialog.Root bind:open={modalState.isOpen}>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="max-w-2xl sm:max-w-2xl">
			<Dialog.Header>
				<Dialog.Title data-testid="modal-title">
					{ticker} Institutional Ownership
				</Dialog.Title>
				<Dialog.Description class="text-xs text-muted-foreground">
					Overview of institutional 13F ownership and quarterly historical filings.
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4 py-2">
				<!-- Top Metrics Cards -->
				<div class="grid grid-cols-3 gap-3">
					<div class="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
						<div class="text-xs font-medium text-muted-foreground">Ownership</div>
						<div class="mt-1 text-lg font-bold" data-testid="current-ownership-metric">
							{formatOwnershipPercent(ownership?.current_ownership_percent)}
						</div>
					</div>
					<div class="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
						<div class="text-xs font-medium text-muted-foreground">Investors</div>
						<div class="mt-1 text-lg font-bold" data-testid="current-investors-metric">
							{formatInvestorCount(ownership?.investors_count)}
						</div>
					</div>
					<div class="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
						<div class="text-xs font-medium text-muted-foreground">Total Invested</div>
						<div class="mt-1 text-lg font-bold" data-testid="current-total-invested-metric">
							{formatTotalInvested(ownership?.total_invested)}
						</div>
					</div>
				</div>

				<!-- Quarterly History Table -->
				<div>
					<div class="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
						Quarterly History
					</div>
					{#if history.length > 0}
						<div class="max-h-60 overflow-y-auto rounded-md border">
							<Table.Root>
								<Table.Header class="bg-muted/40">
									<Table.Row>
										<Table.Head class="text-xs">Filing Date</Table.Head>
										<Table.Head class="text-right text-xs">Ownership %</Table.Head>
										<Table.Head class="text-right text-xs">Investors</Table.Head>
										<Table.Head class="text-right text-xs">Total Invested</Table.Head>
									</Table.Row>
								</Table.Header>
								<Table.Body>
									{#each history as point (point.date)}
										<Table.Row class="hover:bg-muted/30">
											<Table.Cell class="text-xs font-medium tabular-nums">
												{formatDate(point.date)}
											</Table.Cell>
											<Table.Cell class="text-right text-xs tabular-nums">
												{formatOwnershipPercent(point.ownership_percent)}
											</Table.Cell>
											<Table.Cell class="text-right text-xs tabular-nums">
												{formatInvestorCount(point.investors_count)}
											</Table.Cell>
											<Table.Cell class="text-right text-xs tabular-nums">
												{formatTotalInvested(point.total_invested)}
											</Table.Cell>
										</Table.Row>
									{/each}
								</Table.Body>
							</Table.Root>
						</div>
					{:else}
						<div class="rounded-md border p-6 text-center text-sm text-muted-foreground">
							No historical ownership filings available.
						</div>
					{/if}
				</div>
			</div>

			<Dialog.Footer>
				<Button
					data-testid="modal-close-button"
					variant="outline"
					onclick={() => modalState.close()}
				>
					Close
				</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
