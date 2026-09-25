import { describe, it, expect } from 'vitest';
import {
	getChartDateWindow,
	formatDateToISO,
	formatLocalTime,
	formatLocalTickMark,
	formatRelativeTime,
	formatRelativeSyncTime
} from './date';
import { TickMarkType, type UTCTimestamp } from 'lightweight-charts';

describe('getChartDateWindow', () => {
	it('should return a 30-day window for intraday interval 1h', () => {
		const endDate = new Date(2026, 7, 12);
		const result = getChartDateWindow(endDate, '1h');
		expect(result.to).toBe('2026-08-12');
		expect(result.from).toBe('2026-07-13');
	});

	it('should return a 30-day window for intraday interval 4h', () => {
		const endDate = new Date(2026, 7, 12);
		const result = getChartDateWindow(endDate, '4h');
		expect(result.to).toBe('2026-08-12');
		expect(result.from).toBe('2026-07-13');
	});

	it('should return a 2-year window for daily interval 1d', () => {
		const endDate = new Date(2026, 7, 12);
		const result = getChartDateWindow(endDate, '1d');
		expect(result.to).toBe('2026-08-12');
		expect(result.from).toBe('2024-08-12');
	});

	it('should return a 2-year window for weekly interval 1w', () => {
		const endDate = new Date(2026, 7, 12);
		const result = getChartDateWindow(endDate, '1w');
		expect(result.to).toBe('2026-08-12');
		expect(result.from).toBe('2024-08-12');
	});

	it('should return a 2-year window for monthly interval 1m', () => {
		const endDate = new Date(2026, 7, 12);
		const result = getChartDateWindow(endDate, '1m');
		expect(result.to).toBe('2026-08-12');
		expect(result.from).toBe('2024-08-12');
	});

	it('should handle leap year dates gracefully', () => {
		const endDate = new Date(2024, 1, 29); // Feb 29, 2024
		const result = getChartDateWindow(endDate, '1d');
		expect(result.to).toBe('2024-02-29');
		expect(result.from).toBe(formatDateToISO(new Date(2022, 1, 29)));
	});
});

describe('formatLocalTime', () => {
	it('should return date string unchanged for string inputs', () => {
		expect(formatLocalTime('2024-01-10')).toBe('2024-01-10');
	});

	it('should convert numeric Unix timestamps into local time strings', () => {
		const timestamp = 1700000000 as UTCTimestamp;
		const date = new Date(timestamp * 1000);
		const year = date.getFullYear();
		const month = String(date.getMonth() + 1).padStart(2, '0');
		const day = String(date.getDate()).padStart(2, '0');
		const hours = String(date.getHours()).padStart(2, '0');
		const minutes = String(date.getMinutes()).padStart(2, '0');
		const expected = `${year}-${month}-${day} ${hours}:${minutes}`;

		expect(formatLocalTime(timestamp)).toBe(expected);
	});

	it('should handle BusinessDay object input', () => {
		const obj = { year: 2024, month: 1, day: 10 };
		expect(formatLocalTime(obj as never)).toBe('2024-01-10');
	});
});

describe('formatLocalTickMark', () => {
	it('should return null for non-numeric time inputs', () => {
		expect(formatLocalTickMark('2024-01-10', TickMarkType.DayOfMonth, 'en-US')).toBeNull();
		expect(
			formatLocalTickMark(
				{ year: 2024, month: 1, day: 10 } as never,
				TickMarkType.DayOfMonth,
				'en-US'
			)
		).toBeNull();
	});

	it('should format numeric Unix timestamps based on tickMarkType', () => {
		const timestamp = 1700000000 as UTCTimestamp;
		const date = new Date(timestamp * 1000);
		const locale = 'en-US';

		expect(formatLocalTickMark(timestamp, TickMarkType.Year, locale)).toBe(
			date.toLocaleDateString(locale, { year: 'numeric' })
		);
		expect(formatLocalTickMark(timestamp, TickMarkType.Month, locale)).toBe(
			date.toLocaleDateString(locale, { month: 'short' })
		);
		expect(formatLocalTickMark(timestamp, TickMarkType.DayOfMonth, locale)).toBe(
			date.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
		);
		expect(formatLocalTickMark(timestamp, TickMarkType.Time, locale)).toBe(
			date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
		);
		expect(formatLocalTickMark(timestamp, TickMarkType.TimeWithSeconds, locale)).toBe(
			date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
		);
	});
});

describe('formatRelativeTime and formatRelativeSyncTime', () => {
	const fixedNow = new Date('2026-06-15T12:00:00Z');

	describe('formatRelativeTime', () => {
		it('returns empty string for invalid dates', () => {
			expect(formatRelativeTime('invalid-date', fixedNow)).toBe('');
			expect(formatRelativeTime(new Date(NaN), fixedNow)).toBe('');
		});

		it('returns "just now" for future timestamps or clock skew', () => {
			const futureDate = new Date('2026-06-15T12:01:00Z');
			expect(formatRelativeTime(futureDate, fixedNow)).toBe('just now');
		});

		it('returns "just now" for intervals under 60 seconds', () => {
			const justNow = new Date('2026-06-15T11:59:30Z');
			expect(formatRelativeTime(justNow, fixedNow)).toBe('just now');
		});

		it('formats minute intervals correctly ("5m ago")', () => {
			const fiveMinutesAgo = new Date('2026-06-15T11:55:00Z');
			expect(formatRelativeTime(fiveMinutesAgo, fixedNow)).toBe('5m ago');

			const oneMinuteAgo = new Date('2026-06-15T11:59:00Z');
			expect(formatRelativeTime(oneMinuteAgo, fixedNow)).toBe('1m ago');
		});

		it('formats hour intervals with singular and plural forms', () => {
			const oneHourAgo = new Date('2026-06-15T11:00:00Z');
			expect(formatRelativeTime(oneHourAgo, fixedNow)).toBe('1 hour ago');

			const twoHoursAgo = new Date('2026-06-15T10:00:00Z');
			expect(formatRelativeTime(twoHoursAgo, fixedNow)).toBe('2 hours ago');
		});

		it('formats day intervals with singular and plural forms', () => {
			const oneDayAgo = new Date('2026-06-14T12:00:00Z');
			expect(formatRelativeTime(oneDayAgo, fixedNow)).toBe('1 day ago');

			const threeDaysAgo = new Date('2026-06-12T12:00:00Z');
			expect(formatRelativeTime(threeDaysAgo, fixedNow)).toBe('3 days ago');
		});

		it('formats week intervals with singular and plural forms', () => {
			const oneWeekAgo = new Date('2026-06-08T12:00:00Z');
			expect(formatRelativeTime(oneWeekAgo, fixedNow)).toBe('1 week ago');

			const twoWeeksAgo = new Date('2026-06-01T12:00:00Z');
			expect(formatRelativeTime(twoWeeksAgo, fixedNow)).toBe('2 weeks ago');
		});

		it('formats month intervals with singular and plural forms', () => {
			const oneMonthAgo = new Date(fixedNow.getTime() - 30 * 24 * 60 * 60 * 1000);
			expect(formatRelativeTime(oneMonthAgo, fixedNow)).toBe('1 month ago');

			const threeMonthsAgo = new Date(fixedNow.getTime() - 90 * 24 * 60 * 60 * 1000);
			expect(formatRelativeTime(threeMonthsAgo, fixedNow)).toBe('3 months ago');
		});

		it('formats year intervals with singular and plural forms', () => {
			const oneYearAgo = new Date(fixedNow.getTime() - 365 * 24 * 60 * 60 * 1000);
			expect(formatRelativeTime(oneYearAgo, fixedNow)).toBe('1 year ago');

			const twoYearsAgo = new Date(fixedNow.getTime() - 730 * 24 * 60 * 60 * 1000);
			expect(formatRelativeTime(twoYearsAgo, fixedNow)).toBe('2 years ago');
		});
	});

	describe('formatRelativeSyncTime', () => {
		it('returns "Never synced" for null or undefined', () => {
			expect(formatRelativeSyncTime(null, fixedNow)).toBe('Never synced');
			expect(formatRelativeSyncTime(undefined, fixedNow)).toBe('Never synced');
		});

		it('returns "Never synced" for invalid date strings', () => {
			expect(formatRelativeSyncTime('not-a-valid-date', fixedNow)).toBe('Never synced');
		});

		it('returns "Synced just now" for future or current timestamps', () => {
			expect(formatRelativeSyncTime(fixedNow, fixedNow)).toBe('Synced just now');
			const futureDate = new Date(fixedNow.getTime() + 10000);
			expect(formatRelativeSyncTime(futureDate, fixedNow)).toBe('Synced just now');
		});

		it('returns "Synced 5m ago" for 5 minutes in the past', () => {
			const date = new Date(fixedNow.getTime() - 5 * 60 * 1000);
			expect(formatRelativeSyncTime(date, fixedNow)).toBe('Synced 5m ago');
			expect(formatRelativeSyncTime(date.toISOString(), fixedNow)).toBe('Synced 5m ago');
		});

		it('returns "Synced 2 hours ago" for 2 hours in the past', () => {
			const date = new Date(fixedNow.getTime() - 2 * 60 * 60 * 1000);
			expect(formatRelativeSyncTime(date, fixedNow)).toBe('Synced 2 hours ago');
			expect(formatRelativeSyncTime(date.toISOString(), fixedNow)).toBe('Synced 2 hours ago');
		});

		it('returns "Synced 1 day ago" for 1 day in the past', () => {
			const date = new Date(fixedNow.getTime() - 24 * 60 * 60 * 1000);
			expect(formatRelativeSyncTime(date, fixedNow)).toBe('Synced 1 day ago');
		});

		it('returns "Synced 1 week ago" for 7 days in the past', () => {
			const date = new Date(fixedNow.getTime() - 7 * 24 * 60 * 60 * 1000);
			expect(formatRelativeSyncTime(date, fixedNow)).toBe('Synced 1 week ago');
		});
	});
});
