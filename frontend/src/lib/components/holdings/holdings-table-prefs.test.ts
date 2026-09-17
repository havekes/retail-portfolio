import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserPreferencesService, type UserPreferences } from '$lib/api/userPreferencesService';
import {
	loadHoldingsTableConfig,
	saveHoldingsTableConfig,
	type HoldingsTablePrefsService
} from './holdings-table-prefs';
import {
	HOLDINGS_TABLE_DEFAULT_CONFIG,
	HOLDINGS_TABLE_STICKY_COLUMN_ID,
	normalizeHoldingsTableConfig,
	type HoldingsTableConfig
} from './holdings-table-columns';

// Every test injects a mocked service — no real fetch, per frontend/AGENTS.md.
function makeService(prefs: UserPreferences = {}): {
	service: HoldingsTablePrefsService;
	getPreferences: ReturnType<typeof vi.fn>;
	patchPreferences: ReturnType<typeof vi.fn>;
} {
	const getPreferences = vi.fn().mockResolvedValue(prefs);
	const patchPreferences = vi.fn().mockResolvedValue(prefs);
	return { service: { getPreferences, patchPreferences }, getPreferences, patchPreferences };
}

const storedConfig: HoldingsTableConfig = {
	widths: { ...HOLDINGS_TABLE_DEFAULT_CONFIG.widths, quantity: 140 },
	visible: [HOLDINGS_TABLE_STICKY_COLUMN_ID, 'quantity', 'total_value']
};

describe('holdings-table-prefs', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	describe('loadHoldingsTableConfig', () => {
		it('reads the preferences service and normalizes the stored holdings_table key', async () => {
			const { service, getPreferences } = makeService({ holdings_table: storedConfig });

			const config = await loadHoldingsTableConfig(service);

			expect(getPreferences).toHaveBeenCalledTimes(1);
			expect(config).toEqual(normalizeHoldingsTableConfig(storedConfig));
			expect(config.widths.quantity).toBe(140);
			expect(config.visible).toEqual([HOLDINGS_TABLE_STICKY_COLUMN_ID, 'quantity', 'total_value']);
		});

		it('falls back to defaults when the stored config is missing, empty or garbage', async () => {
			const cases: UserPreferences[] = [
				{},
				{ holdings_table: null },
				{ holdings_table: { widths: 5 } as unknown as HoldingsTableConfig }
			];

			for (const prefs of cases) {
				const { service } = makeService(prefs);
				await expect(loadHoldingsTableConfig(service)).resolves.toEqual(
					HOLDINGS_TABLE_DEFAULT_CONFIG
				);
			}
		});

		it('tolerates a rejected getPreferences request', async () => {
			const getPreferences = vi.fn().mockRejectedValue(new Error('network down'));
			const patchPreferences = vi.fn();
			const service: HoldingsTablePrefsService = { getPreferences, patchPreferences };

			await expect(loadHoldingsTableConfig(service)).resolves.toEqual(
				HOLDINGS_TABLE_DEFAULT_CONFIG
			);
			expect(patchPreferences).not.toHaveBeenCalled();
		});
	});

	describe('saveHoldingsTableConfig', () => {
		it('persists a single holdings_table key through patchPreferences', async () => {
			const { service, patchPreferences } = makeService();

			await saveHoldingsTableConfig(service, storedConfig);

			expect(patchPreferences).toHaveBeenCalledTimes(1);
			expect(patchPreferences).toHaveBeenCalledWith({ holdings_table: storedConfig });
		});
	});

	it('round-trips through the real service against the /accounts/me/preferences endpoint', async () => {
		const fetchMock = vi.fn();
		const service = new UserPreferencesService(fetchMock as unknown as typeof fetch);

		fetchMock.mockResolvedValueOnce({
			ok: true,
			json: async () => ({ holdings_table: storedConfig })
		} as Response);

		const loaded = await loadHoldingsTableConfig(service);
		expect(loaded).toEqual(normalizeHoldingsTableConfig(storedConfig));
		expect(fetchMock).toHaveBeenLastCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({ method: 'GET' })
		);

		fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response);
		await saveHoldingsTableConfig(service, loaded);

		expect(fetchMock).toHaveBeenLastCalledWith(
			expect.stringContaining('/accounts/me/preferences'),
			expect.objectContaining({
				method: 'PATCH',
				body: JSON.stringify({ holdings_table: loaded })
			})
		);
	});
});
