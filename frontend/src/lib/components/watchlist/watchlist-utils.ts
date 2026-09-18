import type { SecuritySchema, WatchlistRead } from '$lib/api/marketService';

/**
 * Sorts an array of watchlists according to an array of watchlist IDs.
 * Watchlists present in `order` are sorted to match their index; any watchlists
 * not present in `order` are gracefully appended at the end in their original relative order.
 */
export function sortWatchlistsByOrder<T extends Pick<WatchlistRead, 'id'>>(
	watchlists: T[],
	order?: string[] | null
): T[] {
	if (!order || order.length === 0) {
		return [...watchlists];
	}

	const orderMap = new Map<string, number>();
	order.forEach((id, idx) => orderMap.set(id, idx));

	const inOrder: T[] = [];
	const notInOrder: T[] = [];

	for (const wl of watchlists) {
		if (orderMap.has(wl.id)) {
			inOrder.push(wl);
		} else {
			notInOrder.push(wl);
		}
	}

	inOrder.sort((a, b) => (orderMap.get(a.id) ?? 0) - (orderMap.get(b.id) ?? 0));
	return [...inOrder, ...notInOrder];
}

/**
 * Sorts securities based on sortKey:
 * - 'name_asc': Alphabetical by name ascending
 * - 'name_desc': Alphabetical by name descending
 * - 'price_change_desc': Highest price change percentage first (gainers)
 * - 'price_change_asc': Lowest price change percentage first (losers)
 */
export function sortSecurities(
	securities: SecuritySchema[],
	sortKey?: string | null
): SecuritySchema[] {
	if (!sortKey) {
		return [...securities];
	}

	const list = [...securities];

	switch (sortKey) {
		case 'name_asc':
			return list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
		case 'name_desc':
			return list.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
		case 'price_change_desc':
			return list.sort((a, b) => {
				const aVal = a.daily_price_change_percent;
				const bVal = b.daily_price_change_percent;
				if (aVal == null && bVal == null) return 0;
				if (aVal == null) return 1;
				if (bVal == null) return -1;
				return Number(bVal) - Number(aVal);
			});
		case 'price_change_asc':
			return list.sort((a, b) => {
				const aVal = a.daily_price_change_percent;
				const bVal = b.daily_price_change_percent;
				if (aVal == null && bVal == null) return 0;
				if (aVal == null) return 1;
				if (bVal == null) return -1;
				return Number(aVal) - Number(bVal);
			});
		default:
			return list;
	}
}

/**
 * Formats a price with 2 decimals e.g. "50.25", or "-" when absent.
 */
export function formatPrice(price: number | string | null | undefined): string {
	if (price == null || price === '') {
		return '-';
	}
	const num = typeof price === 'string' ? Number(price) : price;
	if (Number.isNaN(num)) {
		return '-';
	}
	return num.toFixed(2);
}

/**
 * Formats daily percentage change with sign prefix e.g. "+1.65%", "-0.82%", or "0.00%".
 * Returns "-" when absent.
 */
export function formatPriceChangePercent(
	changePercent: number | string | null | undefined
): string {
	if (changePercent == null || changePercent === '') {
		return '-';
	}
	const num = typeof changePercent === 'string' ? Number(changePercent) : changePercent;
	if (Number.isNaN(num)) {
		return '-';
	}
	const formatted = num.toFixed(2);
	if (formatted === '0.00' || formatted === '-0.00') {
		return '0.00%';
	}
	if (num > 0) {
		return `+${formatted}%`;
	}
	return `${formatted}%`;
}
