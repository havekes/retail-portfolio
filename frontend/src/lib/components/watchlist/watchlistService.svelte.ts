import { getMarketService, type MarketService, type WatchlistRead } from '@/api/marketService';
import { getContext, setContext } from 'svelte';

export class WatchlistService {
	watchlists = $state<WatchlistRead[]>([]);
	defaultWatchlistSecurities = $derived(
		this.watchlists.find((w) => w.name === 'Default')?.securities ?? []
	);
	isLoading = $state(false);
	error = $state<string | null>(null);
	private client: MarketService;

	constructor(customFetch?: typeof fetch) {
		this.client = getMarketService(customFetch);
	}

	private handleError(err: unknown, fallback: string): void {
		const message = err instanceof Error ? err.message : String(err);
		this.error = message || fallback;
		console.error(err);
	}

	private replaceWatchlist(updated: WatchlistRead): void {
		this.watchlists = this.watchlists.map((w) => (w.id === updated.id ? updated : w));
	}

	async loadWatchlists(token?: string | null): Promise<void> {
		this.isLoading = true;
		try {
			this.watchlists = await this.client.getWatchlists(token);
		} catch (err) {
			this.handleError(err, 'Failed to load watchlists');
		} finally {
			this.isLoading = false;
		}
	}

	async createWatchlist(name: string, token?: string | null): Promise<void> {
		try {
			const created = await this.client.createWatchlist(name, token);
			this.watchlists = [...this.watchlists, created];
		} catch (err) {
			this.handleError(err, 'Failed to create watchlist');
		}
	}

	async renameWatchlist(watchlistId: string, name: string, token?: string | null): Promise<void> {
		try {
			const updated = await this.client.renameWatchlist(watchlistId, name, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to rename watchlist');
		}
	}

	async deleteWatchlist(watchlistId: string, token?: string | null): Promise<void> {
		try {
			await this.client.deleteWatchlist(watchlistId, token);
			this.watchlists = this.watchlists.filter((w) => w.id !== watchlistId);
		} catch (err) {
			this.handleError(err, 'Failed to delete watchlist');
		}
	}

	async addSecurityToWatchlist(
		watchlistId: string,
		securityId: string,
		token?: string | null
	): Promise<void> {
		try {
			const updated = await this.client.addSecurityToWatchlist(watchlistId, securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to add security to watchlist');
		}
	}

	async removeSecurityFromWatchlist(
		watchlistId: string,
		securityId: string,
		token?: string | null
	): Promise<void> {
		try {
			const updated = await this.client.removeSecurityFromWatchlist(watchlistId, securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to remove security from watchlist');
			await this.loadWatchlists(token);
		}
	}

	hasSecurity(securityId: string): boolean {
		return this.defaultWatchlistSecurities.some((s) => s.id === securityId);
	}

	async toggleSecurity(securityId: string, token?: string | null): Promise<void> {
		const isAdded = this.hasSecurity(securityId);
		try {
			const updated = isAdded
				? await this.client.removeFromWatchlist(securityId, token)
				: await this.client.addToWatchlist(securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to toggle watchlist security');
			await this.loadWatchlists(token);
		}
	}
}

const WATCHLIST_SERVICE_KEY = Symbol('watchlist-service');

export function setWatchlistService() {
	const service = new WatchlistService();
	setContext(WATCHLIST_SERVICE_KEY, service);
	return service;
}

export function getWatchlistService(customFetch?: typeof fetch) {
	if (customFetch) {
		return new WatchlistService(customFetch);
	}
	return getContext<WatchlistService>(WATCHLIST_SERVICE_KEY);
}
