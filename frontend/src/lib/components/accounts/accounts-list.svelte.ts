import { browser } from '$app/environment';
import { accountClient } from '$lib/api/accountClient';
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

	constructor(initialAccounts: Account[] = []) {
		this.accounts = initialAccounts;
		if (browser) {
			this.initWebSocket();
		}
	}

	private initWebSocket() {
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
		// Browsers will send the auth_token cookie automatically if it's the same domain
		// For cross-origin/dev mode, we pass it in the protocols (if HttpOnly is disabled)
		const token = browser
			? document.cookie
					.split('; ')
					.find((row) => row.startsWith('auth_token='))
					?.split('=')[1]
			: null;

		this.ws = token ? new WebSocket(wsUrl, [token]) : new WebSocket(wsUrl);

		this.ws.onopen = () => {
			this.wsConnected = true;
			console.log('WebSocket connected');
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
		} catch (error) {
			this.syncingAccountIds.delete(id);
			this.syncErrors[id] = 'Request failed. Please check your connection.';
			console.error('Failed to sync positions', error);
		}
	}
}
