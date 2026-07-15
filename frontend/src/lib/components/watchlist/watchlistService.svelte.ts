import { getMarketService, type MarketService, type WatchlistRead } from '@/api/marketService';
import { getContext, setContext } from 'svelte';

export class WatchlistService {
	watchlists = $state<WatchlistRead[]>([]);
	isLoading = $state(false);
	error = $state<string | null>(null);
	private client: MarketService;

	constructor(customFetch?: typeof fetch) {
		this.client = getMarketService(customFetch);
	}

	async loadWatchlists(token?: string | null): Promise<void> {
		this.isLoading = true;
		try {
			this.watchlists = await this.client.getWatchlists(token);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to load watchlists';
			console.error(err);
		} finally {
			this.isLoading = false;
		}
	}

	hasSecurity(securityId: string): boolean {
		const defaultWatchlist = this.watchlists.find((w) => w.name === 'Default');
		if (!defaultWatchlist) return false;
		return defaultWatchlist.securities.some((s) => s.id === securityId);
	}

	async toggleSecurity(securityId: string, token?: string | null): Promise<void> {
		const isAdded = this.hasSecurity(securityId);
		try {
			if (isAdded) {
				await this.client.removeFromWatchlist(securityId, token);
				const defaultWatchlist = this.watchlists.find((w) => w.name === 'Default');
				if (defaultWatchlist) {
					defaultWatchlist.securities = defaultWatchlist.securities.filter(
						(s) => s.id !== securityId
					);
				}
			} else {
				const updatedWatchlist = await this.client.addToWatchlist(securityId, token);
				const defaultIndex = this.watchlists.findIndex((w) => w.name === 'Default');
				if (defaultIndex !== -1) {
					this.watchlists[defaultIndex] = updatedWatchlist;
				} else {
					this.watchlists.push(updatedWatchlist);
				}
			}
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to toggle watchlist security';
			console.error(err);
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
