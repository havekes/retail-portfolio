import { describe, it, expect } from 'vitest';
import { INDICATOR_DEFAULTS, type IndicatorId } from './indicator-defaults';

const ALL_IDS: IndicatorId[] = [
	'volume',
	'avgPrice',
	'ma50',
	'ma200',
	'ma50w',
	'ma200w',
	'bb',
	'macd',
	'rsi',
	'obv'
];

describe('INDICATOR_DEFAULTS', () => {
	it('defines every indicator id', () => {
		expect(Object.keys(INDICATOR_DEFAULTS).sort()).toEqual([...ALL_IDS].sort());
	});

	it('keys follow the sidebar render order', () => {
		expect(Object.keys(INDICATOR_DEFAULTS)).toEqual(ALL_IDS);
	});

	it('locks in the canonical MA default colors', () => {
		expect(INDICATOR_DEFAULTS.ma200.color).toBe('#eab308');
		expect(INDICATOR_DEFAULTS.ma50w.color).toBe('#8b5cf6');
		expect(INDICATOR_DEFAULTS.ma200w.color).toBe('#f97316');
	});

	it('enables only avgPrice by default', () => {
		for (const [id, config] of Object.entries(INDICATOR_DEFAULTS)) {
			expect(config.enabled, `${id} enabled flag`).toBe(id === 'avgPrice');
		}
	});

	it('locks in the key numeric settings', () => {
		expect(INDICATOR_DEFAULTS.rsi.period).toBe(14);
		expect(INDICATOR_DEFAULTS.bb.period).toBe(20);
		expect(INDICATOR_DEFAULTS.bb.stdDev).toBe(2);
		expect(INDICATOR_DEFAULTS.macd.fast).toBe(12);
		expect(INDICATOR_DEFAULTS.macd.slow).toBe(26);
		expect(INDICATOR_DEFAULTS.macd.signal).toBe(9);
		expect(INDICATOR_DEFAULTS.ma50.period).toBe(50);
		expect(INDICATOR_DEFAULTS.ma200.period).toBe(200);
	});

	it('gives every entry an empty settings record', () => {
		for (const config of Object.values(INDICATOR_DEFAULTS)) {
			expect(config.settings).toEqual({});
		}
	});
});
