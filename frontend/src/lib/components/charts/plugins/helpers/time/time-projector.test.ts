import { describe, it, expect, vi } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time, UTCTimestamp } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import { TimeProjector } from './time-projector';
import { timeToEpochSeconds } from './time';

const HOUR = 3600;
const DAY = 86400;

const epochOf = (iso: string): number => Math.floor(new Date(iso).getTime() / 1000);

function createCandle(time: Candle['time'], close = 100): Candle {
	return { time, open: close - 1, high: close + 2, low: close - 2, close };
}

/**
 * Builds a chart double whose time scale maps each candle's *native* time shape
 * (epoch numbers or date strings) to `index * spacing`. This mirrors how
 * lightweight-charts keys bars per timeframe and lets a single epoch anchor be
 * resolved against different timeframe fixtures.
 */
function createHarness(candles: Candle[], spacing = 25) {
	const indexByEpoch = new Map<number, number>();
	candles.forEach((candle, index) => indexByEpoch.set(timeToEpochSeconds(candle.time), index));

	const timeScale = {
		timeToCoordinate: vi.fn((time: Time) => {
			const index = indexByEpoch.get(timeToEpochSeconds(time));
			return index === undefined ? null : index * spacing;
		}),
		coordinateToTime: vi.fn((x: number) => {
			const index = Math.round(x / spacing);
			if (index < 0 || index >= candles.length) return null;
			return candles[index].time;
		}),
		coordinateToLogical: vi.fn((x: number) => (x < 0 ? null : x / spacing)),
		logicalToCoordinate: vi.fn((logical: number) => logical * spacing),
		height: vi.fn(() => 30),
		width: vi.fn(() => 750)
	};

	const priceScale = { width: vi.fn(() => 50), applyOptions: vi.fn() };

	const series = {
		priceToCoordinate: vi.fn((price: number) => 200 - price),
		coordinateToPrice: vi.fn((y: number) => 200 - y),
		priceScale: vi.fn(() => priceScale)
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		chartElement: vi.fn(() => document.createElement('div')),
		timeScale: vi.fn(() => timeScale),
		options: vi.fn(() => ({ handleScroll: { pressedMouseMove: true } })),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series, timeScale };
}

function createProjector(candles: Candle[]): {
	projector: TimeProjector;
	harness: ReturnType<typeof createHarness>;
} {
	const harness = createHarness(candles);
	const projector = new TimeProjector();
	projector.attach(harness.chart);
	projector.updateCandles(candles);
	return { projector, harness };
}

describe('TimeProjector epoch anchor resolution', () => {
	describe('daily candles (date-string bars)', () => {
		const candles = [
			createCandle('2024-01-14'),
			createCandle('2024-01-15'),
			createCandle('2024-01-16'),
			createCandle('2024-01-17')
		];

		it('resolves an intraday epoch to the containing daily bar', () => {
			const { projector } = createProjector(candles);
			// 2024-01-15T18:30Z belongs to the 2024-01-15 daily bar (index 1).
			expect(projector.epochToCoordinate(epochOf('2024-01-15T18:30:00Z'))).toBe(25);
		});

		it('resolves an exact-midnight epoch to its own bar', () => {
			const { projector } = createProjector(candles);
			expect(projector.epochToCoordinate(epochOf('2024-01-16T00:00:00Z'))).toBe(50);
		});

		it('clamps anchors before the first candle to the first bar', () => {
			const { projector } = createProjector(candles);
			expect(projector.epochToCoordinate(epochOf('2023-12-01T00:00:00Z'))).toBe(0);
		});

		it('projects anchors beyond the last candle into the future bars', () => {
			const { projector } = createProjector(candles);
			// 3 daily bars beyond 2024-01-17 (index 3) -> logical 6 -> x = 150.
			expect(projector.epochToCoordinate(epochOf('2024-01-20T00:00:00Z'))).toBe(150);
		});

		it('resolves a coordinate back to canonical epoch seconds', () => {
			const { projector } = createProjector(candles);
			expect(projector.coordinateToEpoch(50)).toBe(epochOf('2024-01-16T00:00:00Z'));
		});
	});

	describe('intraday candles (epoch-number bars)', () => {
		const base = epochOf('2024-01-15T00:00:00Z');
		const hourly = Array.from({ length: 12 }, (_, h) =>
			createCandle((base + h * HOUR) as UTCTimestamp)
		);
		const fourHourly = Array.from({ length: 12 }, (_, i) =>
			createCandle((base + i * 4 * HOUR) as UTCTimestamp)
		);

		it('resolves a date anchor to the containing hourly bar', () => {
			const { projector } = createProjector(hourly);
			// 2024-01-15T06:30Z -> 06:00 bar (index 6).
			expect(projector.epochToCoordinate(epochOf('2024-01-15T06:30:00Z'))).toBe(6 * 25);
		});

		it('resolves the same date anchor to the containing 4h bar', () => {
			const { projector } = createProjector(fourHourly);
			// 06:30Z -> 04:00-08:00 bar (index 1).
			expect(projector.epochToCoordinate(epochOf('2024-01-15T06:30:00Z'))).toBe(1 * 25);
		});

		it('resolves a coordinate to the exact bar epoch on an hourly chart', () => {
			const { projector } = createProjector(hourly);
			expect(projector.coordinateToEpoch(3 * 25)).toBe(base + 3 * HOUR);
		});
	});

	describe('longer timeframes (week/month-start bars)', () => {
		const weekly = [
			createCandle('2024-01-08'), // Monday
			createCandle('2024-01-15'),
			createCandle('2024-01-22')
		];
		const monthly = [
			createCandle('2024-01-01'),
			createCandle('2024-02-01'),
			createCandle('2024-03-01')
		];

		it('resolves a mid-week anchor to the containing weekly bar', () => {
			const { projector } = createProjector(weekly);
			expect(projector.epochToCoordinate(epochOf('2024-01-17T00:00:00Z'))).toBe(25);
		});

		it('resolves a mid-month anchor to the containing monthly bar', () => {
			const { projector } = createProjector(monthly);
			expect(projector.epochToCoordinate(epochOf('2024-02-20T00:00:00Z'))).toBe(25);
		});

		it('keeps a drawing date inside the same period across timeframes', () => {
			const anchorEpoch = epochOf('2024-01-17T00:00:00Z');
			const daily = [createCandle('2024-01-17'), createCandle('2024-01-18')];
			const { projector: dailyProjector } = createProjector(daily);
			const { projector: weeklyProjector } = createProjector(weekly);

			// Daily: the exact date; weekly: the Monday that starts that week.
			expect(dailyProjector.epochToCoordinate(anchorEpoch)).toBe(0);
			expect(weeklyProjector.epochToCoordinate(anchorEpoch)).toBe(25);
		});
	});

	it('returns null for non-finite epochs or when the chart is detached', () => {
		const { projector } = createProjector([createCandle('2024-01-15')]);
		expect(projector.epochToCoordinate(NaN)).toBeNull();

		const detached = new TimeProjector();
		detached.updateCandles([createCandle('2024-01-15')]);
		expect(detached.epochToCoordinate(epochOf('2024-01-15T00:00:00Z'))).toBeNull();
		expect(detached.coordinateToEpoch(0)).toBeNull();
	});

	it('falls back to the time scale lookup when no candle data is retained', () => {
		const candles = [createCandle('2024-01-15'), createCandle('2024-01-16')];
		const harness = createHarness(candles);
		const projector = new TimeProjector();
		projector.attach(harness.chart);
		// No updateCandles(): the raw epoch is handed to the time scale.
		expect(projector.epochToCoordinate(epochOf('2024-01-16T00:00:00Z'))).toBe(25);
	});

	it('resolves future anchors consistently via logical bar indices', () => {
		const base = epochOf('2024-01-15T00:00:00Z');
		const daily = [createCandle('2024-01-15'), createCandle('2024-01-16')];
		const { projector } = createProjector(daily);
		// 1 daily bar past the last (index 1) -> logical 2 -> x = 50.
		expect(projector.epochToCoordinate(base + 2 * DAY)).toBe(50);
		// 2 daily bars past the last -> logical 3 -> x = 75.
		expect(projector.epochToCoordinate(base + 3 * DAY)).toBe(75);
	});
});
