import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	UserPreferencesService,
	getUserPreferencesService,
	type UserPreferences
} from './userPreferencesService';
import { mergeChartPreferences } from '$lib/chart-preferences';
import { GlobalSidebarState } from '$lib/components/ui/sidebar/context.svelte';

describe('UserPreferencesService', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		global.fetch = vi.fn();
	});

	it('getPreferences fetches from /accounts/me/preferences with method GET', async () => {
		const mockPrefs: UserPreferences = {
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			},
			sidebar_open: true
		};

		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			json: async () => mockPrefs
		} as Response);

		const service = getUserPreferencesService();
		const res = await service.getPreferences();

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({ method: 'GET' })
		);
		expect(res).toEqual(mockPrefs);
		expect(res.sidebar_open).toBe(true);
	});

	it('getPreferences supports tokenOverride header', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			json: async () => ({ sidebar_open: false })
		} as Response);

		const service = getUserPreferencesService();
		const res = await service.getPreferences('custom-token-123');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				headers: expect.objectContaining({
					Authorization: 'Bearer custom-token-123'
				})
			})
		);
		expect(res.sidebar_open).toBe(false);
	});

	it('savePreferences sends PUT request with body to /accounts/me/preferences', async () => {
		const mockPrefs: UserPreferences = {
			timeframe: '1d',
			chart_style: 'candlestick',
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			},
			sidebar_open: false
		};

		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			json: async () => mockPrefs
		} as Response);

		const service = new UserPreferencesService();
		const res = await service.savePreferences(mockPrefs);

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify(mockPrefs)
			})
		);
		expect(res).toEqual(mockPrefs);
		expect(res.sidebar_open).toBe(false);
	});

	it('savePreferences supports tokenOverride header', async () => {
		const mockPrefs: UserPreferences = { sidebar_open: true };

		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			json: async () => mockPrefs
		} as Response);

		const service = new UserPreferencesService();
		await service.savePreferences(mockPrefs, 'save-token-456');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				method: 'PUT',
				headers: expect.objectContaining({
					Authorization: 'Bearer save-token-456'
				})
			})
		);
	});

	it('getPreferences resolves an empty {} response without throwing', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			json: async () => ({})
		} as Response);

		const service = getUserPreferencesService();
		const res = await service.getPreferences();

		expect(res).toEqual({});
	});

	it('mergeChartPreferences preserves sidebar_open when updating chart preferences', () => {
		const initial: UserPreferences = {
			timeframe: '1d',
			chart_style: 'candlestick',
			sidebar_open: false,
			indicators: {
				rsi: { enabled: true, color: '#00ff00', settings: { period: 14 } }
			}
		};

		const updated = mergeChartPreferences(initial, { timeframe: '4h' });
		expect(updated.timeframe).toBe('4h');
		expect(updated.sidebar_open).toBe(false);
		expect(updated.chart_style).toBe('candlestick');
		expect(updated.indicators?.rsi?.enabled).toBe(true);
	});

	it('mergeChartPreferences preserves other preferences when updating sidebar_open', () => {
		const initial: UserPreferences = {
			timeframe: '1d',
			chart_style: 'heikin_ashi',
			sidebar_open: true,
			indicators: {
				rsi: { enabled: true, color: '#00ff00', settings: { period: 14 } }
			}
		};

		const updated = mergeChartPreferences(initial, { sidebar_open: false });
		expect(updated.sidebar_open).toBe(false);
		expect(updated.timeframe).toBe('1d');
		expect(updated.chart_style).toBe('heikin_ashi');
		expect(updated.indicators?.rsi?.enabled).toBe(true);
	});

	it('GlobalSidebarState initializes with provided value or defaults to true', () => {
		const defaultState = new GlobalSidebarState();
		expect(defaultState.open).toBe(true);

		const closedState = new GlobalSidebarState(false);
		expect(closedState.open).toBe(false);

		closedState.open = true;
		expect(closedState.open).toBe(true);
	});
});
