import { TickMarkType, type Time } from 'lightweight-charts';

export function formatDateToISO(date: Date): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

export function getDateRange(daysBack: number): { from: string; to: string } {
	const today = new Date();
	const past = new Date(today);
	past.setDate(today.getDate() - daysBack);
	return {
		from: formatDateToISO(past),
		to: formatDateToISO(today)
	};
}

export function formatDate(dateString: string | Date): string {
	const date = typeof dateString === 'string' ? new Date(dateString) : dateString;
	return date.toLocaleDateString('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	});
}

export function getChartDateWindow(endDate: Date, interval: string): { from: string; to: string } {
	const isIntraday = interval === '1h' || interval === '4h';
	const fromDate = new Date(endDate);

	if (isIntraday) {
		fromDate.setDate(fromDate.getDate() - 30);
	} else {
		fromDate.setFullYear(fromDate.getFullYear() - 2);
	}

	return {
		from: formatDateToISO(fromDate),
		to: formatDateToISO(endDate)
	};
}

export function formatLocalTime(time: Time): string {
	if (typeof time !== 'number') {
		if (typeof time === 'string') return time;
		return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
	}

	const date = new Date(time * 1000);
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	const hours = String(date.getHours()).padStart(2, '0');
	const minutes = String(date.getMinutes()).padStart(2, '0');

	return `${year}-${month}-${day} ${hours}:${minutes}`;
}

export function formatLocalTickMark(
	time: Time,
	tickMarkType: TickMarkType,
	locale: string
): string | null {
	if (typeof time !== 'number') {
		return null;
	}

	const date = new Date(time * 1000);

	switch (tickMarkType) {
		case TickMarkType.Year:
			return date.toLocaleDateString(locale, { year: 'numeric' });
		case TickMarkType.Month:
			return date.toLocaleDateString(locale, { month: 'short' });
		case TickMarkType.DayOfMonth:
			return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
		case TickMarkType.Time:
			return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
		case TickMarkType.TimeWithSeconds:
			return date.toLocaleTimeString(locale, {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			});
		default:
			return date.toLocaleString(locale);
	}
}

/**
 * Formats a date relative to now into a compact human-readable string:
 * - < 60s (or future/clock skew): "just now"
 * - < 60m: "Xm ago" (e.g., "5m ago")
 * - < 24h: "X hour ago" / "X hours ago" (e.g., "1 hour ago", "2 hours ago")
 * - < 7d: "X day ago" / "X days ago" (e.g., "1 day ago", "3 days ago")
 * - < 30d: "X week ago" / "X weeks ago" (e.g., "1 week ago", "2 weeks ago")
 * - < 365d: "X month ago" / "X months ago" (e.g., "1 month ago", "3 months ago")
 * - >= 365d: "X year ago" / "X years ago" (e.g., "1 year ago", "2 years ago")
 */
export function formatRelativeTime(date: Date | string, now: Date = new Date()): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	if (isNaN(d.getTime())) return '';

	const diffMs = now.getTime() - d.getTime();
	if (diffMs < 60_000) return 'just now';

	const minutes = Math.floor(diffMs / 60_000);
	if (minutes < 60) return `${minutes}m ago`;

	const hours = Math.floor(diffMs / 3600_000);
	if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;

	const days = Math.floor(diffMs / 86400_000);
	if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`;

	const weeks = Math.floor(days / 7);
	if (days < 30) return `${weeks} ${weeks === 1 ? 'week' : 'weeks'} ago`;

	const months = Math.floor(days / 30);
	if (days < 365) return `${months} ${months === 1 ? 'month' : 'months'} ago`;

	const years = Math.floor(days / 365);
	return `${years} ${years === 1 ? 'year' : 'years'} ago`;
}

/**
 * Formats the last sync timestamp into a user-friendly label.
 * Returns "Never synced" when date is null, undefined, or invalid,
 * or "Synced <relative>" (e.g., "Synced just now", "Synced 5m ago", "Synced 2 hours ago").
 */
export function formatRelativeSyncTime(
	date: Date | string | null | undefined,
	now: Date = new Date()
): string {
	if (!date) return 'Never synced';
	const rel = formatRelativeTime(date, now);
	if (!rel) return 'Never synced';
	return `Synced ${rel}`;
}
