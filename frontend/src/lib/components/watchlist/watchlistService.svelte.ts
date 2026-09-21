import {
	getMarketService,
	type MarketSearchResult,
	type MarketService,
	type WatchlistRead
} from '@/api/marketService';
import { getContext, setContext } from 'svelte';

export class WatchlistService {
	watchlists = $state<WatchlistRead[]>([]);
	defaultWatchlist = $derived(this.watchlists.find((w) => w.name === 'Default') ?? null);
	defaultWatchlistSecurities = $derived(this.defaultWatchlist?.securities ?? []);
	activeWatchlistId = $state<string | null>(null);
	activeWatchlist = $derived(this.watchlists.find((w) => w.id === this.activeWatchlistId) ?? null);
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
		this.error = null;
		this.isLoading = true;
		try {
			this.watchlists = await this.client.getWatchlists(token);
		} catch (err) {
			this.handleError(err, 'Failed to load watchlists');
		} finally {
			this.isLoading = false;
		}
	}

	selectWatchlist(watchlistId: string): void {
		this.activeWatchlistId = watchlistId;
	}

	async searchSecurities(query: string): Promise<MarketSearchResult[]> {
		return await this.client.search(query);
	}

	async addSecurity(
		watchlistId: string,
		result: MarketSearchResult,
		token?: string | null
	): Promise<void> {
		this.error = null;
		try {
			const target = this.watchlists.find((w) => w.id === watchlistId);
			if (
				target?.securities.some(
					(s) =>
						s.symbol.toUpperCase() === result.code.toUpperCase() &&
						s.exchange.toUpperCase() === result.exchange.toUpperCase()
				)
			) {
				return;
			}

			let securityId: string | undefined;
			for (const w of this.watchlists) {
				const match = w.securities.find(
					(s) =>
						s.symbol.toUpperCase() === result.code.toUpperCase() &&
						s.exchange.toUpperCase() === result.exchange.toUpperCase()
				);
				if (match) {
					securityId = match.id;
					break;
				}
			}

			if (!securityId) {
				const resolved = await this.client.createOrUpdateSecurity({
					code: result.code,
					exchange: result.exchange,
					name: result.name,
					currency: 'USD'
				});
				securityId = resolved.security_id;
			}

			const updated = await this.client.addSecurityToWatchlist(watchlistId, securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to add security to watchlist');
		}
	}

	async removeSecurity(
		watchlistId: string,
		securityId: string,
		token?: string | null
	): Promise<void> {
		this.error = null;
		try {
			const updated = await this.client.removeSecurityFromWatchlist(watchlistId, securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to remove security from watchlist');
		}
	}

	async createWatchlist(name: string, token?: string | null): Promise<void> {
		this.error = null;
		try {
			const created = await this.client.createWatchlist(name, token);
			this.watchlists = [...this.watchlists, created];
		} catch (err) {
			this.handleError(err, 'Failed to create watchlist');
		}
	}

	async renameWatchlist(watchlistId: string, name: string, token?: string | null): Promise<void> {
		this.error = null;
		try {
			const updated = await this.client.renameWatchlist(watchlistId, name, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			this.handleError(err, 'Failed to rename watchlist');
		}
	}

	async deleteWatchlist(watchlistId: string, token?: string | null): Promise<void> {
		this.error = null;
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
		this.error = null;
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
		this.error = null;
		try {
			const updated = await this.client.removeSecurityFromWatchlist(watchlistId, securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			// Resync first: the resync clears the shared error at its start, so the
			// removal error must be recorded afterwards to stay visible.
			await this.loadWatchlists(token);
			this.handleError(err, 'Failed to remove security from watchlist');
		}
	}

	hasSecurity(securityId: string): boolean {
		return this.defaultWatchlistSecurities.some((s) => s.id === securityId);
	}

	async toggleSecurity(securityId: string, token?: string | null): Promise<void> {
		this.error = null;
		const isAdded = this.hasSecurity(securityId);
		try {
			const updated = isAdded
				? await this.client.removeFromWatchlist(securityId, token)
				: await this.client.addToWatchlist(securityId, token);
			this.replaceWatchlist(updated);
		} catch (err) {
			// Resync first: the resync clears the shared error at its start, so the
			// toggle error must be recorded afterwards to stay visible.
			await this.loadWatchlists(token);
			this.handleError(err, 'Failed to toggle watchlist security');
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
