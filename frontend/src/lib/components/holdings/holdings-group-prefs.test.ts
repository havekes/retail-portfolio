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
		it('accepts stock mode and legacy company mode (normalizing to stock), falling back to none otherwise', () => {
			expect(normalizeHoldingsGroupMode('stock')).toBe('stock');
			expect(normalizeHoldingsGroupMode('company')).toBe('stock');
			expect(normalizeHoldingsGroupMode('none')).toBe('none');

			for (const raw of [undefined, null, '', 'STOCK', 'COMPANY', 1, {}, []]) {
				expect(normalizeHoldingsGroupMode(raw)).toBe('none');
			}
		});
	});

	describe('loadHoldingsGroupMode', () => {
		it('reads the preferences service and returns normalized stock mode for stock and company keys', async () => {
			const stockService = makeService({ holdings_group: 'stock' });
			await expect(loadHoldingsGroupMode(stockService.service)).resolves.toBe('stock');

			const companyService = makeService({ holdings_group: 'company' });
			await expect(loadHoldingsGroupMode(companyService.service)).resolves.toBe('stock');
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

			await saveHoldingsGroupMode(service, 'stock');

			expect(patchPreferences).toHaveBeenCalledTimes(1);
			expect(patchPreferences).toHaveBeenCalledWith({ holdings_group: 'stock' });
		});
	});

	it('round-trips through the real service against the /accounts/me/preferences endpoint', async () => {
		const fetchMock = vi.fn();
		const service = new UserPreferencesService(fetchMock as unknown as typeof fetch);

		fetchMock.mockResolvedValueOnce({
			ok: true,
			json: async () => ({ holdings_group: 'stock' })
		} as Response);

		await expect(loadHoldingsGroupMode(service)).resolves.toBe('stock');
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
