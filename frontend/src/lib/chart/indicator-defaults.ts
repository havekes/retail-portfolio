import { AVG_PRICE_LINE_COLOR } from '$lib/components/charts/colors';

export type IndicatorId =
	'volume' | 'avgPrice' | 'ma50' | 'ma200' | 'ma50w' | 'ma200w' | 'bb' | 'macd' | 'rsi' | 'obv';

export interface IndicatorDefault {
	label: string;
	color: string;
	period: number;
	enabled: boolean;
	stdDev?: number;
	fast?: number;
	slow?: number;
	signal?: number;
	settings: Record<string, unknown>;
}

/**
 * Single source of truth for the default state of every indicator.
 * Key order matches the indicator sidebar render order — do not reorder.
 */
export const INDICATOR_DEFAULTS: Record<IndicatorId, IndicatorDefault> = deepFreeze({
	volume: { label: 'Volume', color: '#64748b', period: 0, enabled: false, settings: {} },
	avgPrice: {
		label: 'Avg Price',
		color: AVG_PRICE_LINE_COLOR,
		period: 0,
		enabled: true,
		settings: {}
	},
	ma50: { label: '50 Day MA', color: '#3b82f6', period: 50, enabled: false, settings: {} },
	ma200: { label: '200 Day MA', color: '#eab308', period: 200, enabled: false, settings: {} },
	ma50w: { label: '50 Week MA', color: '#8b5cf6', period: 50, enabled: false, settings: {} },
	ma200w: { label: '200 Week MA', color: '#f97316', period: 200, enabled: false, settings: {} },
	bb: {
		label: 'Bollinger Bands',
		color: '#8b5cf6',
		period: 20,
		stdDev: 2,
		enabled: false,
		settings: {}
	},
	macd: {
		label: 'MACD',
		color: '#ef4444',
		period: 0,
		fast: 12,
		slow: 26,
		signal: 9,
		enabled: false,
		settings: {}
	},
	rsi: { label: 'RSI', color: '#06b6d4', period: 14, enabled: false, settings: {} },
	obv: { label: 'OBV', color: '#f59e0b', period: 0, enabled: false, settings: {} }
});

/**
 * Recursively deep-freezes the record, each entry, and each entry's nested
 * `settings` record so accidental mutation throws instead of silently
 * corrupting the shared defaults.
 */
function deepFreeze<T extends object>(obj: T): T {
	for (const value of Object.values(obj)) {
		if (value && typeof value === 'object') deepFreeze(value);
	}
	return Object.freeze(obj);
}

/**
 * Return an independent, fully-owned copy of the indicator defaults — the
 * returned entries (including nested `settings`) share no references with
 * `INDICATOR_DEFAULTS`, so mutating a returned entry never leaks into the
 * frozen defaults.
 */
export function createIndicatorConfigs(): Record<IndicatorId, IndicatorDefault> {
	return Object.fromEntries(
		Object.entries(INDICATOR_DEFAULTS).map(([id, d]) => [id, { ...d, settings: { ...d.settings } }])
	) as Record<IndicatorId, IndicatorDefault>;
}
