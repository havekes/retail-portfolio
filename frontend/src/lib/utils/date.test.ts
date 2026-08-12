import { describe, it, expect } from 'vitest';
import { getChartDateWindow, formatDateToISO } from './date';

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
