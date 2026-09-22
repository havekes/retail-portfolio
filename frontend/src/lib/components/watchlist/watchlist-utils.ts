import type { WatchlistRead, WatchlistSecuritySchema, WatchlistSort } from '$lib/api/marketService';

const WATCHLIST_SORT_KEYS: WatchlistSort[] = [
	'custom',
	'name_asc',
	'price_change_desc',
	'price_change_asc',
	'date_added',
	'date_added_asc'
];

/**
 * Narrows a persisted (or absent) watchlist sort key to the known `WatchlistSort`
 * union. Anything unrecognised — including `undefined`/`null` from older payloads —
 * falls back to `custom`.
 */
export function normalizeWatchlistSort(sort?: string | null): WatchlistSort {
	return WATCHLIST_SORT_KEYS.includes(sort as WatchlistSort) ? (sort as WatchlistSort) : 'custom';
}

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
 * Returns a new array with the item at `from` moved to index `to` (index shift).
 * Never mutates the input. Equal or out-of-range indices are a no-op that still
 * returns a fresh copy, so callers can assign the result unconditionally.
 */
export function moveItem<T>(list: T[], from: number, to: number): T[] {
	const next = [...list];
	if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) {
		return next;
	}
	const [moved] = next.splice(from, 1);
	next.splice(to, 0, moved);
	return next;
}

/**
 * Shared keyboard handler for reorderable lists: ArrowUp/ArrowDown shift the item
 * at `index` by one position via `onMove(from, to)`. The arrow key is always
 * consumed (`preventDefault`) so the page does not scroll, but moving past either
 * end is a no-op. Any other key returns `false` untouched.
 */
export function handleReorderKeydown(
	event: { key: string; preventDefault(): void },
	index: number,
	length: number,
	onMove: (from: number, to: number) => void
): boolean {
	const direction = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
	if (direction === 0) {
		return false;
	}

	event.preventDefault();
	const target = index + direction;
	if (target >= 0 && target < length) {
		onMove(index, target);
	}
	return true;
}

/**
 * Sorts securities based on sortKey:
 * - 'custom': Insertion order, ascending `position` (oldest added first)
 * - 'name_asc': Alphabetical by name ascending
 * - 'name_desc': Alphabetical by name descending
 * - 'price_change_desc': Highest price change percentage first (gainers)
 * - 'price_change_asc': Lowest price change percentage first (losers)
 * - 'date_added': Most recently added first (descending `added_at`)
 * - 'date_added_asc': Oldest first (ascending `added_at`)
 *
 * Absent or unrecognised keys fall back to the custom (`position`) order.
 */
export function sortSecurities(
	securities: WatchlistSecuritySchema[],
	sortKey?: string | null
): WatchlistSecuritySchema[] {
	const list = [...securities];
	const byPosition = (a: WatchlistSecuritySchema, b: WatchlistSecuritySchema) =>
		(a.position ?? 0) - (b.position ?? 0);

	switch (sortKey) {
		case 'custom':
			return list.sort(byPosition);
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
		case 'date_added':
			return list.sort((a, b) => (b.added_at ?? '').localeCompare(a.added_at ?? ''));
		case 'date_added_asc':
			return list.sort((a, b) => (a.added_at ?? '').localeCompare(b.added_at ?? ''));
		default:
			// Absent or unrecognised keys (including stale ones) fall back to custom order.
			return list.sort(byPosition);
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

/**
 * Formats a security's `added_at` timestamp for display, e.g. "Jan 1, 2024".
 * Explicit `en-US` locale and UTC time zone keep the output deterministic
 * regardless of the viewer's environment. Returns `null` when the value is
 * absent or unparseable so callers can omit the element entirely.
 */
export function formatDateAdded(added: string | null | undefined): string | null {
	if (added == null || added === '') {
		return null;
	}
	const date = new Date(added);
	if (Number.isNaN(date.getTime())) {
		return null;
	}
	return date.toLocaleDateString('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric',
		timeZone: 'UTC'
	});
}
