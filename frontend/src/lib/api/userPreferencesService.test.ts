import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserPreferencesService, getUserPreferencesService } from './userPreferencesService';

describe('UserPreferencesService', () => {
	let service: UserPreferencesService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		service = getUserPreferencesService();
	});

	it('getPreferences fetches from /accounts/me/preferences with method GET', async () => {
		const mockPrefs = {
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			}
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPrefs
		} as Response);

		const res = await service.getPreferences();
		expect(res).toEqual(mockPrefs);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('savePreferences sends PUT request with body to /accounts/me/preferences', async () => {
		const mockPrefs = {
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			}
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPrefs
		} as Response);

		const res = await service.savePreferences(mockPrefs);
		expect(res).toEqual(mockPrefs);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify(mockPrefs)
			})
		);
	});

	it('getPreferences resolves an empty {} response without throwing', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({})
		} as Response);

		const res = await service.getPreferences();
		expect(res).toEqual({});
	});
});
