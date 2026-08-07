import { describe, it, expect } from 'vitest';
import type { IndicatorConfig, IndicatorSettings } from './indicatorsService';
import { buildIndicatorEntry, buildToggleEntry } from './buildIndicatorEntry';

describe('buildIndicatorEntry', () => {
	it('builds enabled from newConfig when present', () => {
		const entry = buildIndicatorEntry({ enabled: true }, undefined);
		expect(entry.enabled).toBe(true);
	});

	it('falls back to current.enabled when newConfig lacks enabled', () => {
		const current: IndicatorConfig = { enabled: false, color: '#000', settings: {} };
		const entry = buildIndicatorEntry({}, current);
		expect(entry.enabled).toBe(false);
	});

	it('defaults enabled to false when both are absent', () => {
		const entry = buildIndicatorEntry({}, undefined);
		expect(entry.enabled).toBe(false);
	});

	it('builds color from newConfig when present', () => {
		const entry = buildIndicatorEntry({ enabled: true, color: '#ff0000' }, undefined);
		expect(entry.color).toBe('#ff0000');
	});

	it('falls back to current.color when newConfig lacks color', () => {
		const current: IndicatorConfig = { enabled: true, color: '#00ff00', settings: {} };
		const entry = buildIndicatorEntry({ enabled: true }, current);
		expect(entry.color).toBe('#00ff00');
	});

	it('defaults color to empty string when both are absent', () => {
		const entry = buildIndicatorEntry({}, undefined);
		expect(entry.color).toBe('');
	});

	it('promotes period into settings', () => {
		const entry = buildIndicatorEntry({ period: 21 }, undefined);
		expect(entry.settings.period).toBe(21);
	});

	it('promotes stdDev into settings', () => {
		const entry = buildIndicatorEntry({ stdDev: 3 }, undefined);
		expect(entry.settings.stdDev).toBe(3);
	});

	it('promotes fast/slow/signal into settings for MACD', () => {
		const entry = buildIndicatorEntry({ fast: 6, slow: 13, signal: 5 }, undefined);
		expect(entry.settings.fast).toBe(6);
		expect(entry.settings.slow).toBe(13);
		expect(entry.settings.signal).toBe(5);
	});

	it('preserves existing settings keys that are not overridden', () => {
		const current: IndicatorConfig = {
			enabled: true,
			color: '#ababab',
			settings: { period: 14, customKey: 'val' } as IndicatorSettings
		};
		const entry = buildIndicatorEntry({ fast: 6 }, current);
		expect(entry.settings.period).toBe(14);
		expect(entry.settings.customKey).toBe('val');
		expect(entry.settings.fast).toBe(6);
	});

	it('overrides existing settings when newConfig provides same key', () => {
		const current: IndicatorConfig = {
			enabled: true,
			color: '#ababab',
			settings: { period: 14 } as IndicatorSettings
		};
		const entry = buildIndicatorEntry({ period: 21 }, current);
		expect(entry.settings.period).toBe(21);
	});

	it('promotes all numeric fields together with enabled/color', () => {
		const entry = buildIndicatorEntry(
			{ enabled: true, color: '#f00', period: 14, fast: 12, slow: 26, signal: 9 },
			undefined
		);
		expect(entry.enabled).toBe(true);
		expect(entry.color).toBe('#f00');
		expect(entry.settings.period).toBe(14);
		expect(entry.settings.fast).toBe(12);
		expect(entry.settings.slow).toBe(26);
		expect(entry.settings.signal).toBe(9);
	});
});

describe('buildToggleEntry', () => {
	it('inverts enabled from current', () => {
		const current: IndicatorConfig = { enabled: true, color: '#f00', settings: {} };
		const entry = buildToggleEntry(current, '#fff', undefined);
		expect(entry.enabled).toBe(false);
	});

	it('inverts enabled from defaultEnabled when current is absent', () => {
		const entry = buildToggleEntry(undefined, '#fff', true);
		expect(entry.enabled).toBe(false);
	});

	it('falls back to indicatorColor when current has no color', () => {
		const entry = buildToggleEntry(undefined, '#3b82f6', undefined);
		expect(entry.color).toBe('#3b82f6');
	});

	it('preserves current color and settings', () => {
		const current: IndicatorConfig = {
			enabled: false,
			color: '#ff0000',
			settings: { period: 21 } as IndicatorSettings
		};
		const entry = buildToggleEntry(current, '#fff', undefined);
		expect(entry.enabled).toBe(true);
		expect(entry.color).toBe('#ff0000');
		expect(entry.settings.period).toBe(21);
	});
});
