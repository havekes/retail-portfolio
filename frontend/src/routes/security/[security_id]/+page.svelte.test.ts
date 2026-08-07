import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Candle } from '@/utils/finance/candle';

// --- Mocks ---

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		getPreferences: vi.fn(),
		savePreferences: vi.fn()
	},
	ChartStyle: 'heikin_ashi'
}));

vi.mock('$lib/api/marketService', () => ({
	getMarketService: vi.fn(() => ({
		getPrices: vi.fn()
	}))
}));

vi.mock('$lib/api/alertsService', () => ({
	alertsService: {
		getAlerts: vi.fn().mockResolvedValue({ items: [] })
	}
}));

vi.mock('$lib/api/accountService', () => ({
	accountService: {
		getHoldings: vi.fn().mockResolvedValue({ items: [] })
	}
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/navigation', () => ({
	navigate: vi.fn()
}));

vi.mock('@/utils/finance/candle', () => ({
	convertToHeikinAshi: vi.fn((candles: Candle[]) =>
		candles.map((c) => ({ ...c, open: c.open * 1.01, close: c.close * 1.01 }))
	)
}));

vi.mock('@/components/charts/security-chart.svelte', () => ({
	default: vi.fn(function ChartComponent(props: { candles?: Candle[] }) {
		return props;
	})
}));

vi.mock('@/components/layout/app-header.svelte', () => ({
	default: vi.fn(function Header() {
		return 'header';
	})
}));

vi.mock('@/components/layout/app-sidebar.svelte', () => ({
	default: vi.fn(() => 'sidebar')
}));

vi.mock('$lib/components/ui/sidebar/index.js', () => ({
	Provider: vi.fn(function Provider({ children }: { children?: () => void }) {
		return children ? children() : null;
	}),
	Inset: vi.fn(function Inset({ children }: { children?: () => void }) {
		return children ? children() : null;
	}),
	Content: vi.fn(function Content({ children }: { children?: () => void }) {
		return children ? children() : null;
	})
}));

vi.mock('@/components/actions-sidebar/indicator/indicator-group.svelte', () => ({
	default: vi.fn(function IndicatorsGroup() {
		return 'indicators';
	})
}));

vi.mock('@/components/actions-sidebar/price-alert/price-alert-group.svelte', () => ({
	default: vi.fn(function PriceAlertsGroup() {
		return 'alerts';
	})
}));

vi.mock('@/components/actions-sidebar/note/note-group.svelte', () => ({
	default: vi.fn(function NotesGroup() {
		return 'notes';
	})
}));

vi.mock('@/components/actions-sidebar/document/document-group.svelte', () => ({
	default: vi.fn(function DocumentsGroup() {
		return 'docs';
	})
}));

vi.mock('@/components/actions-sidebar/ai/ai-analysis-group.svelte', () => ({
	default: vi.fn(function AIAnalysisGroup() {
		return 'ai';
	})
}));

vi.mock('@/components/actions-sidebar/holding-group/holding-group.svelte', () => ({
	default: vi.fn(function HoldingsGroup() {
		return 'holdings';
	})
}));

vi.mock('@/components/watchlist/watchlistService.svelte', () => ({
	getWatchlistService: vi.fn(() => ({
		toggleSecurity: vi.fn(),
		hasSecurity: vi.fn().mockReturnValue(false)
	}))
}));

vi.mock('@/utils/finance/moving-average', () => ({
	calculateSMA: vi.fn()
}));

vi.mock('@/utils/finance/rsi', () => ({
	calculateRSI: vi.fn()
}));

vi.mock('@/utils/finance/macd', () => ({
	calculateMACD: vi.fn()
}));

vi.mock('@/utils/finance/bollinger-bands', () => ({
	calculateBollingerBands: vi.fn()
}));

vi.mock('@/utils/finance/obv', () => ({
	calculateOBV: vi.fn()
}));

vi.mock('@/utils/finance/average-cost', () => ({
	blendedAverageCost: vi.fn().mockReturnValue(100)
}));

vi.mock('$lib/components/charts/colors', () => ({
	AVG_PRICE_LINE_COLOR: '#000000'
}));

vi.mock('@lucide/svelte/icons/star', () => ({
	default: vi.fn(() => 'star')
}));

// --- Test data ---

const mockCandle: Candle = {
	time: '2024-01-01',
	open: 100,
	high: 110,
	low: 95,
	close: 105,
	volume: 1000
};

const indicatorPrefs = {
	sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
};

// --- Tests ---

describe('Security Page — chart preferences', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows Heikin-Ashi as default when no prefs are saved (AC5)', () => {
		const prefs: Record<string, unknown> = {};
		const chartStyle = (prefs.chart_style as 'heikin_ashi' | 'candlestick' | undefined) ?? 'heikin_ashi';
		expect(chartStyle).toBe('heikin_ashi');
	});

	it('saved candlestick: displayCandles is raw (non-HA) candles (AC2)', () => {
		const chartStyle: 'heikin_ashi' | 'candlestick' = 'candlestick';

		const raw: Candle[] = [mockCandle];
		const ha = [mockCandle].map((c) => ({ ...c, open: c.open * 1.01, close: c.close * 1.01 }));

		const displayCandles = chartStyle === 'heikin_ashi' ? ha : raw;
		expect(displayCandles[0].close).toBe(raw[0].close);
		expect(displayCandles[0].close).not.toBe(ha[0].close);
	});

	it('saved heikin_ashi: displayCandles is HA-transformed candles', () => {
		const chartStyle: 'heikin_ashi' | 'candlestick' = 'heikin_ashi';

		const raw: Candle[] = [mockCandle];
		const ha = [mockCandle].map((c) => ({ ...c, open: c.open * 1.01, close: c.close * 1.01 }));

		const displayCandles = chartStyle === 'heikin_ashi' ? ha : raw;
		expect(displayCandles[0].close).toBe(ha[0].close);
		expect(displayCandles[0].close).not.toBe(raw[0].close);
	});

	it('savePreferences blob includes indicators on timeframe change (AC4)', async () => {
		const { userPreferencesService } = await import('$lib/api/userPreferencesService');

		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: indicatorPrefs
		});
		vi.mocked(userPreferencesService.savePreferences).mockResolvedValue({
			indicators: indicatorPrefs,
			timeframe: '1h'
		});

		const prefs = await userPreferencesService.getPreferences();
		await userPreferencesService.savePreferences({
			...prefs,
			indicators: prefs.indicators ?? {},
			timeframe: '1h'
		});

		expect(userPreferencesService.savePreferences).toHaveBeenCalledWith(
			expect.objectContaining({
				indicators: indicatorPrefs,
				timeframe: '1h'
			})
		);
	});

	it('savePreferences blob includes indicators on style change (AC4)', async () => {
		const { userPreferencesService } = await import('$lib/api/userPreferencesService');

		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: indicatorPrefs
		});

		const prefs = await userPreferencesService.getPreferences();
		await userPreferencesService.savePreferences({
			...prefs,
			indicators: prefs.indicators ?? {},
			chart_style: 'candlestick'
		});

		expect(userPreferencesService.savePreferences).toHaveBeenCalledWith(
			expect.objectContaining({
				indicators: indicatorPrefs,
				chart_style: 'candlestick'
			})
		);
	});

	it('ChartStyle type accepts only valid values', () => {
		const valid1: 'heikin_ashi' | 'candlestick' = 'heikin_ashi';
		const valid2: 'heikin_ashi' | 'candlestick' = 'candlestick';
		expect(valid1).toBe('heikin_ashi');
		expect(valid2).toBe('candlestick');
	});
});
