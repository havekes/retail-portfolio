import { browser } from '$app/environment';
import { accountClient } from '$lib/api/accountClient';
import { authService } from '$lib/api/authService';
import {
	type Account,
	type AccountGroupKeys,
	getInstitutionLabel,
	getAccountTypeLabel,
	type Institution,
	type AccountType
} from '@/types/account';
import { SvelteSet } from 'svelte/reactivity';
import { group, type GroupBy } from '@/group';
import { WsEventType, type AccountSyncMessage } from '@/types/websocket';

export class AccountsListState {
	accounts = $state<Account[]>([]);
	isLoading = $state(false);

	selectionMode = $state(false);
	selectedAccounts = $state<string[]>([]);
	groupBy = $state<GroupBy>('none');

	// Track which accounts are currently syncing
	syncingAccountIds = $state(new SvelteSet<string>());

	// Track which accounts have sync errors
	syncErrors = $state<Record<string, string | null>>({});

	groupByLabels: Record<GroupBy, string> = {
		none: 'None',
		institution: 'Institution',
		accountType: 'Account type'
	};

	wsConnected = $state(false);

	private ws: WebSocket | null = null;
	private syncStatusHydrated = false;

	constructor(initialAccounts: Account[] = []) {
		this.accounts = initialAccounts;
		if (browser) {
			this.initWebSocket();
		}
	}

	private async initWebSocket() {
		let wsUrl: string;
		const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

		if (apiBaseUrl && apiBaseUrl.startsWith('http')) {
			const isHttps = apiBaseUrl.startsWith('https');
			const protocol = isHttps ? 'wss:' : 'ws:';
			const host = apiBaseUrl.replace(/^https?:\/\//, '').split('/')[0];
			wsUrl = `${protocol}//${host}/api/ws`;
		} else {
			const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
			wsUrl = `${protocol}//${window.location.host}/api/ws`;
		}

		console.log('Connecting to WebSocket:', wsUrl);
		const ticket = await authService
			.getWsTicket()
			.then((data) => data?.ticket ?? null)
			.catch(() => null);

		if (!ticket) {
			console.warn('Failed to obtain WebSocket ticket. Aborting connection.');
			return;
		}

		this.ws = new WebSocket(`${wsUrl}?ticket=${encodeURIComponent(ticket)}`);

		this.ws.onopen = () => {
			this.wsConnected = true;
			console.log('WebSocket connected');
			this.hydrateSyncStatus();
		};

		this.ws.onmessage = async (event) => {
			console.log('WebSocket message received:', event.data);
			try {
				const data = JSON.parse(event.data);
				const accountId = (data as AccountSyncMessage).account_id;
				if (data.type === WsEventType.SYNC_STARTED) {
					console.log('Sync started for account:', accountId);
					this.syncingAccountIds.add(accountId);
					this.syncErrors[accountId] = null;
				} else if (data.type === WsEventType.SYNC_FINISHED) {
					console.log('Sync finished for account:', accountId);
					this.syncingAccountIds.delete(accountId);
					this.syncErrors[accountId] = null;
				} else if (data.type === WsEventType.SYNC_FAILED) {
					console.log('Sync failed for account:', accountId);
					this.syncingAccountIds.delete(accountId);
					this.syncErrors[accountId] = 'Failed to sync. Please try again.';
				}
			} catch (e) {
				console.error('Failed to parse websocket message', e);
			}
		};

		this.ws.onclose = () => {
			this.wsConnected = false;
			this.syncStatusHydrated = false;
			console.log('WebSocket disconnected');
			// Reconnect logic
			setTimeout(() => this.initWebSocket(), 5000);
		};
	}

	destroy() {
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}

	private async hydrateSyncStatus() {
		if (this.syncStatusHydrated) {
			return;
		}
		this.syncStatusHydrated = true;
		try {
			const { account_ids } = await accountClient.getSyncStatus();
			for (const id of account_ids) {
				this.syncingAccountIds.add(id);
			}
		} catch (error) {
			console.error('Failed to hydrate sync status', error);
		}
	}

	async fetchAccounts() {
		this.isLoading = true;
		try {
			this.accounts = await accountClient.getAccounts();
		} finally {
			this.isLoading = false;
		}
	}

	isCreatePortfolioDisabled = $derived(this.selectionMode && this.selectedAccounts.length === 0);

	groupedAccounts = $derived.by(async () => {
		let key: AccountGroupKeys | null = null;
		if (this.groupBy === 'institution') key = 'institution_id';
		else if (this.groupBy === 'accountType') key = 'account_type_id';

		// Re-wrap accountList in a Promise because group expects Promise<T[]>
		const groupsMap = await group(Promise.resolve(this.accounts), key);

		const result = [];
		for (const [keyValue, groupAccounts] of groupsMap) {
			let label;
			if (this.groupBy === 'institution' && keyValue !== null) {
				label = getInstitutionLabel(keyValue as Institution);
			} else if (this.groupBy === 'accountType' && keyValue !== null) {
				label = getAccountTypeLabel(keyValue as AccountType);
			} else {
				label = 'All Accounts';
			}

			result.push({
				key: keyValue,
				label,
				accounts: groupAccounts
			});
		}
		return result;
	});

	toggleSelectionMode() {
		this.selectionMode = true;
	}

	cancelSelection() {
		this.selectionMode = false;
		this.selectedAccounts = [];
	}

	createPortfolio() {
		console.log(this.selectedAccounts);
		this.selectionMode = false;
		this.selectedAccounts = [];
	}

	handleCreatePortfolioClick() {
		if (this.selectionMode) {
			this.createPortfolio();

			return;
		}

		this.toggleSelectionMode();
	}

	toggleAccountSelection(id: string) {
		if (this.selectedAccounts.includes(id)) {
			this.selectedAccounts = this.selectedAccounts.filter((accId) => accId !== id);
		} else {
			this.selectedAccounts = [...this.selectedAccounts, id];
		}
	}

	async syncAccount(id: string) {
		this.syncingAccountIds.add(id);
		this.syncErrors[id] = null;
		try {
			await accountClient.syncPositions(id);
			// Verify the job completed; WS message may be lost if Redis pub/sub fails
			await this.waitForSyncFinish(id);
		} catch (error) {
			this.syncingAccountIds.delete(id);
			this.syncErrors[id] = 'Request failed. Please check your connection.';
			console.error('Failed to sync positions', error);
		}
	}

	private async waitForSyncFinish(id: string, timeoutMs = 60000, intervalMs = 1500) {
		const deadline = Date.now() + timeoutMs;
		while (Date.now() < deadline) {
			await new Promise((r) => setTimeout(r, intervalMs));
			try {
				const { account_ids } = await accountClient.getSyncStatus();
				if (!account_ids.includes(id)) {
					// Sync finished on backend but no WS message arrived yet.
					// Don't clear state here — let the WS message (SYNC_FINISHED or
					// SYNC_FAILED) be the source of truth for success/failure.
					// If the WS never delivers a message, the timeout below will fire.
					return;
				}
			} catch {
				// If status endpoint is unavailable, keep waiting
			}
		}
		// Timeout — WS never delivered a finish/failure message. Show an error
		// but keep the spinner so the user knows the outcome is uncertain.
		this.syncErrors[id] = 'Sync took too long. Check account status.';
	}
}
