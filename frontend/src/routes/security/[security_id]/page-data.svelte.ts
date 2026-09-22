import { SvelteDate } from 'svelte/reactivity';
import { getMarketService, type MarketPrice, type SecuritySchema } from '$lib/api/marketService';
import { getChartDateWindow } from '$lib/utils/date';

/**
 * Layer-2 state for the security route: owns the post-navigation data wave (the
 * security identity plus the default `1d` price series) so `+page.svelte` can
 * render its shell before either resolves.
 *
 * Instantiate per page (SSR "no global instances" rule) — never export an instance.
 */
export class SecurityPageDataService {
	security = $state<SecuritySchema | null>(null);
	items = $state<MarketPrice[] | null>(null);
	isLoading = $state(true);
	error = $state<string | null>(null);

	private client = getMarketService();
	// Guards against a stale in-flight load clobbering a newer soft navigation.
	private loadSeq = 0;

	/**
	 * Fetch the security identity and its `1d` price series in parallel.
	 *
	 * Never throws: returns the caught error so callers can route a 401 through the
	 * shared async-data seam, or `null` when the load succeeded. A missing/empty
	 * series is a successful load whose message lands in `error`.
	 */
	async load(securityId: string): Promise<unknown | null> {
		const seq = ++this.loadSeq;

		this.security = null;
		this.items = null;
		this.error = null;
		this.isLoading = true;

		try {
			const { from, to } = getChartDateWindow(new SvelteDate(), '1d');

			const [security, priceResponse] = await Promise.all([
				this.client.getSecurity(securityId),
				this.client.getPrices(securityId, from, to, '1d')
			]);

			if (seq !== this.loadSeq) return null;

			this.security = security;

			if (!priceResponse.items || priceResponse.items.length === 0) {
				this.error = 'No price data available for this security';
				return null;
			}

			this.items = priceResponse.items;

			return null;
		} catch (err) {
			if (seq !== this.loadSeq) return null;

			this.error = err instanceof Error ? err.message : String(err);

			return err;
		} finally {
			if (seq === this.loadSeq) {
				this.isLoading = false;
			}
		}
	}
}
