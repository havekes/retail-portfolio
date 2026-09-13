<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { accountClient } from '$lib/api/accountClient';
	import { brokerClient } from '$lib/api/brokerClient';
	import type { BackendInstitution } from '@/types/broker/broker';
	import type { CsvDiscoveredAccount } from '@/types/account';
	import type { ModalState } from '@/utils/modal-state.svelte';
	import Upload from '@lucide/svelte/icons/upload';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import FileSpreadsheet from '@lucide/svelte/icons/file-spreadsheet';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import AlertCircle from '@lucide/svelte/icons/alert-circle';

	let {
		open = $bindable(false),
		modalState,
		onSuccess
	}: {
		open?: boolean;
		modalState?: ModalState<void>;
		onSuccess?: () => void;
	} = $props();

	let step = $state<1 | 2>(1);
	let institutions = $state<BackendInstitution[]>([]);
	let selectedInstitutionId = $state<string>('');
	let selectedFile = $state<File | null>(null);
	let detectedAccounts = $state<CsvDiscoveredAccount[]>([]);
	let selectedAccountNumbers = $state<string[]>([]);
	let accountCurrencies = $state<Record<string, string>>({});
	let isLoading = $state(false);
	let error = $state<string | null>(null);
	let isDragging = $state(false);

	const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

	let isModalOpen = $derived(modalState ? modalState.isOpen : open);

	let prevOpen = false;
	$effect(() => {
		const currentOpen = isModalOpen;
		if (currentOpen && !prevOpen) {
			resetState();
			loadInstitutions();
		} else if (!currentOpen && prevOpen) {
			resetState();
		}
		prevOpen = currentOpen;
	});

	function resetState() {
		step = 1;
		selectedFile = null;
		detectedAccounts = [];
		selectedAccountNumbers = [];
		accountCurrencies = {};
		error = null;
		isLoading = false;
		isDragging = false;
		if (institutions.length === 1) {
			selectedInstitutionId = institutions[0].id;
		}
	}

	function closeModal() {
		if (modalState) {
			modalState.close();
		}
		open = false;
		resetState();
	}

	async function loadInstitutions() {
		try {
			const all = await brokerClient.getAvailableInstitutions();
			institutions = all.filter((i) => i.csv_import_enabled === true);
			if (institutions.length === 1 && !selectedInstitutionId) {
				selectedInstitutionId = institutions[0].id;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load institutions.';
		}
	}

	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
	}

	function validateAndSetFile(file: File) {
		error = null;
		if (!file.name.toLowerCase().endsWith('.csv')) {
			error = 'Please select a valid CSV file (.csv).';
			selectedFile = null;
			return;
		}

		if (file.size > MAX_FILE_SIZE) {
			error = 'File size exceeds 10MB limit.';
			selectedFile = null;
			return;
		}

		selectedFile = file;
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		validateAndSetFile(file);
		input.value = '';
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (!isLoading) {
			isDragging = true;
		}
	}

	function handleDragLeave(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
		if (isLoading) return;

		const file = e.dataTransfer?.files?.[0];
		if (file) {
			validateAndSetFile(file);
		}
	}

	async function handleInspect() {
		if (!selectedInstitutionId || !selectedFile || isLoading) return;

		isLoading = true;
		error = null;

		try {
			const accounts = await accountClient.inspectCsv(selectedInstitutionId, selectedFile);
			if (!accounts || accounts.length === 0) {
				error = 'No accounts discovered in CSV file.';
				return;
			}
			detectedAccounts = accounts;
			selectedAccountNumbers = accounts.map((acc) => acc.account_number);
			accountCurrencies = {};
			for (const acc of accounts) {
				accountCurrencies[acc.account_number] = acc.currency || 'CAD';
			}
			step = 2;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to inspect CSV file.';
		} finally {
			isLoading = false;
		}
	}

	let areAllSelected = $derived(
		detectedAccounts.length > 0 && selectedAccountNumbers.length === detectedAccounts.length
	);

	let isIndeterminate = $derived(
		selectedAccountNumbers.length > 0 && selectedAccountNumbers.length < detectedAccounts.length
	);

	function toggleSelectAll() {
		if (areAllSelected) {
			selectedAccountNumbers = [];
		} else {
			selectedAccountNumbers = detectedAccounts.map((acc) => acc.account_number);
		}
	}

	function toggleAccount(accountNumber: string) {
		if (selectedAccountNumbers.includes(accountNumber)) {
			selectedAccountNumbers = selectedAccountNumbers.filter((no) => no !== accountNumber);
		} else {
			selectedAccountNumbers = [...selectedAccountNumbers, accountNumber];
		}
	}

	async function handleImport() {
		if (
			!selectedInstitutionId ||
			!selectedFile ||
			selectedAccountNumbers.length === 0 ||
			isLoading
		) {
			return;
		}

		isLoading = true;
		error = null;

		try {
			await accountClient.importAccountsCsv(
				selectedInstitutionId,
				selectedFile,
				selectedAccountNumbers,
				accountCurrencies
			);
			closeModal();
			onSuccess?.();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to import accounts.';
		} finally {
			isLoading = false;
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			if (step === 1 && selectedInstitutionId && selectedFile && !isLoading) {
				e.preventDefault();
				handleInspect();
			} else if (step === 2 && selectedAccountNumbers.length > 0 && !isLoading) {
				e.preventDefault();
				handleImport();
			}
		}
	}
</script>

<Dialog.Root
	open={isModalOpen}
	onOpenChange={(openVal) => {
		if (!openVal) {
			closeModal();
		} else {
			if (modalState) modalState.open();
			open = true;
		}
	}}
>
	<Dialog.Portal>
		<Dialog.Overlay />
		<Dialog.Content class="sm:max-w-[720px]" onkeydown={handleKeyDown}>
			<Dialog.Header>
				<Dialog.Title>
					{step === 1 ? 'Import accounts from CSV' : 'Select accounts to import'}
				</Dialog.Title>
				<Dialog.Description>
					{step === 1
						? 'Upload a CSV export from your broker to discover and import accounts.'
						: 'Select accounts to import. Existing accounts in the app will have their holdings updated, while new accounts will be created.'}
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-4 py-2">
				{#if error}
					<Alert.Root variant="destructive">
						<AlertCircle class="h-4 w-4" />
						<Alert.Title>Error</Alert.Title>
						<Alert.Description>{error}</Alert.Description>
					</Alert.Root>
				{/if}

				{#if step === 1}
					<div class="space-y-4">
						<div class="space-y-2">
							<Label for="broker-select">Select broker</Label>
							<select
								id="broker-select"
								bind:value={selectedInstitutionId}
								disabled={isLoading}
								class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs transition-colors focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
							>
								<option value="" disabled>Select a broker...</option>
								{#each institutions as inst (inst.id)}
									<option value={inst.id}>{inst.name}</option>
								{/each}
							</select>
						</div>

						<div class="space-y-2">
							<Label for="csv-file-input">Select CSV file</Label>
							<div
								class="flex flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-colors {isDragging
									? 'border-primary bg-primary/5'
									: 'border-input hover:border-primary/50'}"
								ondragover={handleDragOver}
								ondragleave={handleDragLeave}
								ondrop={handleDrop}
								role="region"
								aria-label="CSV file dropzone"
							>
								<label for="csv-file-input" class="flex cursor-pointer flex-col items-center gap-2">
									<Upload class="h-8 w-8 text-muted-foreground" />
									<span class="text-sm font-medium text-foreground">
										Click to select or drag CSV file here
									</span>
									<span class="text-xs text-muted-foreground"> CSV files up to 10MB </span>
									<Input
										id="csv-file-input"
										type="file"
										accept=".csv,text/csv"
										onchange={handleFileSelect}
										class="hidden"
										disabled={isLoading}
									/>
								</label>
							</div>
						</div>

						{#if selectedFile}
							<div
								class="flex items-center justify-between rounded-md border border-input bg-accent/30 p-3"
								data-testid="selected-file-container"
							>
								<div class="flex items-center gap-2 truncate">
									<FileSpreadsheet class="h-4 w-4 shrink-0 text-muted-foreground" />
									<span class="truncate text-sm font-medium" data-testid="selected-file-name">
										{selectedFile.name}
									</span>
								</div>
								<span
									class="ml-2 shrink-0 text-xs text-muted-foreground"
									data-testid="selected-file-size"
								>
									{formatFileSize(selectedFile.size)}
								</span>
							</div>
						{/if}
					</div>
				{:else if step === 2}
					<div class="space-y-4">
						<div class="max-h-[340px] overflow-y-auto rounded-md border">
							<Table.Root>
								<Table.Header>
									<Table.Row>
										<Table.Head class="w-[50px]">
											<Checkbox
												checked={areAllSelected}
												indeterminate={isIndeterminate}
												onCheckedChange={toggleSelectAll}
												aria-label="Select all accounts"
												disabled={isLoading}
											/>
										</Table.Head>
										<Table.Head>Account #</Table.Head>
										<Table.Head>Name</Table.Head>
										<Table.Head>Type</Table.Head>
										<Table.Head>Action</Table.Head>
										<Table.Head>Currency</Table.Head>
										<Table.Head class="text-right">Holdings</Table.Head>
									</Table.Row>
								</Table.Header>
								<Table.Body>
									{#each detectedAccounts as acc (acc.account_number)}
										<Table.Row>
											<Table.Cell>
												<Checkbox
													checked={selectedAccountNumbers.includes(acc.account_number)}
													onCheckedChange={() => toggleAccount(acc.account_number)}
													aria-label={`Select account ${acc.account_number}`}
													disabled={isLoading}
												/>
											</Table.Cell>
											<Table.Cell class="font-mono text-sm">{acc.account_number}</Table.Cell>
											<Table.Cell class="font-medium">{acc.account_name}</Table.Cell>
											<Table.Cell>{acc.account_type_name}</Table.Cell>
											<Table.Cell>
												{#if acc.exists}
													<Badge
														variant="outline"
														class="border-blue-500/30 bg-blue-50 text-xs font-normal text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
														data-testid="account-action-badge"
													>
														Update holdings
													</Badge>
												{:else}
													<Badge
														variant="outline"
														class="border-green-500/30 bg-green-50 text-xs font-normal text-green-700 dark:bg-green-950/40 dark:text-green-300"
														data-testid="account-action-badge"
													>
														Create account
													</Badge>
												{/if}
											</Table.Cell>
											<Table.Cell>
												<select
													value={accountCurrencies[acc.account_number] ?? acc.currency ?? 'CAD'}
													onchange={(e) => {
														accountCurrencies[acc.account_number] = (
															e.target as HTMLSelectElement
														).value;
													}}
													class="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm focus:ring-1 focus:ring-ring focus:outline-none"
													disabled={isLoading}
													data-testid="account-currency-select"
													aria-label={`Currency for ${acc.account_name}`}
												>
													<option value="CAD">CAD</option>
													<option value="USD">USD</option>
													<option value="EUR">EUR</option>
													<option value="GBP">GBP</option>
													<option value="AUD">AUD</option>
													<option value="CHF">CHF</option>
													<option value="JPY">JPY</option>
												</select>
											</Table.Cell>
											<Table.Cell class="text-right">{acc.positions_count}</Table.Cell>
										</Table.Row>
									{/each}
								</Table.Body>
							</Table.Root>
						</div>
					</div>
				{/if}
			</div>

			<Dialog.Footer class="flex items-center justify-between sm:justify-between">
				{#if step === 1}
					<div></div>
					<div class="flex gap-2">
						<Button onclick={closeModal} variant="outline" disabled={isLoading}>Cancel</Button>
						<Button
							onclick={handleInspect}
							disabled={!selectedInstitutionId || !selectedFile || isLoading}
						>
							{#if isLoading}
								<Loader2 class="mr-2 h-4 w-4 animate-spin" />
								Inspecting...
							{:else}
								Preview accounts
							{/if}
						</Button>
					</div>
				{:else if step === 2}
					<div>
						<Button
							onclick={() => {
								step = 1;
								error = null;
							}}
							variant="outline"
							disabled={isLoading}
						>
							<ArrowLeft class="mr-2 h-4 w-4" />
							Back
						</Button>
					</div>
					<div class="flex gap-2">
						<Button onclick={closeModal} variant="outline" disabled={isLoading}>Cancel</Button>
						<Button
							onclick={handleImport}
							disabled={selectedAccountNumbers.length === 0 || isLoading}
						>
							{#if isLoading}
								<Loader2 class="mr-2 h-4 w-4 animate-spin" />
								Importing...
							{:else}
								Import selected ({selectedAccountNumbers.length})
							{/if}
						</Button>
					</div>
				{/if}
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
