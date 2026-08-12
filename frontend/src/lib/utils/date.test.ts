import { describe, it, expect } from 'vitest';
import { getChartDateWindow, formatDateToISO, formatLocalTime, formatLocalTickMark } from './date';
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
		expect(formatLocalTime(obj as never)).toBe(JSON.stringify(obj));
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
