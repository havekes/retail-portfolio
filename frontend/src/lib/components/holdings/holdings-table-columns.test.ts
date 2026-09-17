import { describe, it, expect } from 'vitest';
import {
	HOLDINGS_TABLE_COLUMN_IDS,
	HOLDINGS_TABLE_COLUMN_MAX_WIDTHS,
	HOLDINGS_TABLE_COLUMN_MIN_WIDTHS,
	HOLDINGS_TABLE_DEFAULT_CONFIG,
	HOLDINGS_TABLE_DEFAULT_WIDTHS,
	HOLDINGS_TABLE_STICKY_COLUMN_ID,
	clampColumnWidth,
	normalizeHoldingsTableConfig
} from './holdings-table-columns';

describe('holdings-table-columns', () => {
	describe('clampColumnWidth', () => {
		it('returns the width unchanged when it is within bounds', () => {
			expect(clampColumnWidth('quantity', 120)).toBe(120);
		});

		it('clamps below the per-column minimum and above the per-column maximum', () => {
			expect(clampColumnWidth('quantity', 0)).toBe(HOLDINGS_TABLE_COLUMN_MIN_WIDTHS.quantity);
			expect(clampColumnWidth('quantity', 10_000)).toBe(HOLDINGS_TABLE_COLUMN_MAX_WIDTHS.quantity);

			expect(clampColumnWidth('security_symbol', 1)).toBe(
				HOLDINGS_TABLE_COLUMN_MIN_WIDTHS.security_symbol
			);
			expect(clampColumnWidth('security_symbol', 10_000)).toBe(
				HOLDINGS_TABLE_COLUMN_MAX_WIDTHS.security_symbol
			);
		});

		it('rounds fractional widths and falls back to the default for non-finite input', () => {
			expect(clampColumnWidth('account_name', 140.6)).toBe(141);
			expect(clampColumnWidth('account_name', Number.NaN)).toBe(
				HOLDINGS_TABLE_DEFAULT_WIDTHS.account_name
			);
			expect(clampColumnWidth('account_name', Number.POSITIVE_INFINITY)).toBe(
				HOLDINGS_TABLE_DEFAULT_WIDTHS.account_name
			);
		});
	});

	describe('normalizeHoldingsTableConfig', () => {
		it('falls back to the defaults for missing, null or non-object input', () => {
			expect(normalizeHoldingsTableConfig(undefined)).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
			expect(normalizeHoldingsTableConfig(null)).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
			expect(normalizeHoldingsTableConfig('garbage')).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
			expect(normalizeHoldingsTableConfig([])).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
			expect(normalizeHoldingsTableConfig(42)).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
			expect(normalizeHoldingsTableConfig({})).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
		});

		it('merges stored widths over the defaults and drops unknown column ids', () => {
			const config = normalizeHoldingsTableConfig({
				widths: { quantity: 150, account_name: 175, not_a_column: 999 }
			});

			expect(config.widths.quantity).toBe(150);
			expect(config.widths.account_name).toBe(175);
			expect(config.widths.security_symbol).toBe(HOLDINGS_TABLE_DEFAULT_WIDTHS.security_symbol);
			expect(config.widths).not.toHaveProperty('not_a_column');
		});

		it('clamps out-of-range and ignores invalid width values', () => {
			const config = normalizeHoldingsTableConfig({
				widths: { quantity: 5, total_value: 10_000, profit_loss: 'wide', latest_price: Number.NaN }
			});

			expect(config.widths.quantity).toBe(HOLDINGS_TABLE_COLUMN_MIN_WIDTHS.quantity);
			expect(config.widths.total_value).toBe(HOLDINGS_TABLE_COLUMN_MAX_WIDTHS.total_value);
			expect(config.widths.profit_loss).toBe(HOLDINGS_TABLE_DEFAULT_WIDTHS.profit_loss);
			expect(config.widths.latest_price).toBe(HOLDINGS_TABLE_DEFAULT_WIDTHS.latest_price);
		});

		it('filters unknown/duplicate visible ids and keeps canonical column order', () => {
			const config = normalizeHoldingsTableConfig({
				visible: ['profit_loss', 'bogus', 'security_symbol', 'profit_loss']
			});

			expect(config.visible).toEqual(['security_symbol', 'profit_loss']);
		});

		it('always keeps the sticky first column visible', () => {
			const config = normalizeHoldingsTableConfig({ visible: ['quantity'] });

			expect(config.visible).toContain(HOLDINGS_TABLE_STICKY_COLUMN_ID);
			expect(config.visible).toEqual(['security_symbol', 'quantity']);
		});

		it('falls back to all columns visible when the stored list is empty or invalid', () => {
			expect(normalizeHoldingsTableConfig({ visible: [] }).visible).toEqual([
				...HOLDINGS_TABLE_COLUMN_IDS
			]);
			expect(normalizeHoldingsTableConfig({ visible: ['nope'] }).visible).toEqual([
				...HOLDINGS_TABLE_COLUMN_IDS
			]);
			expect(normalizeHoldingsTableConfig({ visible: 'quantity' }).visible).toEqual([
				...HOLDINGS_TABLE_COLUMN_IDS
			]);
		});

		it('round-trips a saved config through serialize/parse unchanged', () => {
			const config = normalizeHoldingsTableConfig({
				widths: { security_symbol: 260, quantity: 140 },
				visible: ['security_symbol', 'quantity', 'total_value']
			});

			const restored = normalizeHoldingsTableConfig(JSON.parse(JSON.stringify(config)));
			expect(restored).toEqual(config);
		});

		it('returns a fresh object that does not alias the defaults', () => {
			const config = normalizeHoldingsTableConfig(undefined);
			config.widths.quantity = 999;
			config.visible.push('profit_loss');

			expect(HOLDINGS_TABLE_DEFAULT_CONFIG.widths.quantity).toBe(
				HOLDINGS_TABLE_DEFAULT_WIDTHS.quantity
			);
			expect(HOLDINGS_TABLE_DEFAULT_CONFIG.visible).toHaveLength(HOLDINGS_TABLE_COLUMN_IDS.length);
		});
	});
});
