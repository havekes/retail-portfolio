import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserPreferencesService, type UserPreferences } from '$lib/api/userPreferencesService';
import {
	loadHoldingsGroupMode,
	saveHoldingsGroupMode,
	normalizeHoldingsGroupMode,
	type HoldingsGroupPrefsService
} from './holdings-group-prefs';

// Every test injects a mocked service — no real fetch, per frontend/AGENTS.md.
function makeService(prefs: UserPreferences = {}): {
	service: HoldingsGroupPrefsService;
	getPreferences: ReturnType<typeof vi.fn>;
	patchPreferences: ReturnType<typeof vi.fn>;
} {
	const getPreferences = vi.fn().mockResolvedValue(prefs);
	const patchPreferences = vi.fn().mockResolvedValue(prefs);
	return { service: { getPreferences, patchPreferences }, getPreferences, patchPreferences };
}

describe('holdings-group-prefs', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	describe('normalizeHoldingsGroupMode', () => {
		it('accepts the explicit company mode and falls back to none otherwise', () => {
			expect(normalizeHoldingsGroupMode('company')).toBe('company');
			expect(normalizeHoldingsGroupMode('none')).toBe('none');

			for (const raw of [undefined, null, '', 'COMPANY', 1, {}, []]) {
				expect(normalizeHoldingsGroupMode(raw)).toBe('none');
			}
		});
	});

	describe('loadHoldingsGroupMode', () => {
		it('reads the preferences service and returns the stored holdings_group key', async () => {
			const { service, getPreferences } = makeService({ holdings_group: 'company' });

			await expect(loadHoldingsGroupMode(service)).resolves.toBe('company');
			expect(getPreferences).toHaveBeenCalledTimes(1);
		});

		it('falls back to none when the stored key is missing, empty or garbage', async () => {
			const cases: UserPreferences[] = [
				{},
				{ holdings_group: null },
				{ holdings_group: 'garbage' as never }
			];

			for (const prefs of cases) {
				const { service } = makeService(prefs);
				await expect(loadHoldingsGroupMode(service)).resolves.toBe('none');
			}
		});

		it('tolerates a rejected getPreferences request', async () => {
			const getPreferences = vi.fn().mockRejectedValue(new Error('network down'));
			const patchPreferences = vi.fn();
			const service: HoldingsGroupPrefsService = { getPreferences, patchPreferences };

			await expect(loadHoldingsGroupMode(service)).resolves.toBe('none');
			expect(patchPreferences).not.toHaveBeenCalled();
		});
	});

	describe('saveHoldingsGroupMode', () => {
		it('persists a single holdings_group key through patchPreferences', async () => {
			const { service, patchPreferences } = makeService();

			await saveHoldingsGroupMode(service, 'company');

			expect(patchPreferences).toHaveBeenCalledTimes(1);
			expect(patchPreferences).toHaveBeenCalledWith({ holdings_group: 'company' });
		});
	});

	it('round-trips through the real service against the /accounts/me/preferences endpoint', async () => {
		const fetchMock = vi.fn();
		const service = new UserPreferencesService(fetchMock as unknown as typeof fetch);

		fetchMock.mockResolvedValueOnce({
			ok: true,
			json: async () => ({ holdings_group: 'company' })
		} as Response);

		await expect(loadHoldingsGroupMode(service)).resolves.toBe('company');
		expect(fetchMock).toHaveBeenLastCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({ method: 'GET' })
		);

		fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response);
		await saveHoldingsGroupMode(service, 'none');

		expect(fetchMock).toHaveBeenLastCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				method: 'PATCH',
				body: JSON.stringify({ holdings_group: 'none' })
			})
		);
	});
});
