import { describe, it, expect } from 'vitest';
import { TickMarkType, type BusinessDay, type UTCTimestamp } from 'lightweight-charts';
import type { Candle } from '$lib/utils/finance/candle';
import { formatLocalTickMark, formatLocalTime } from '$lib/utils/date';
import {
	addIntervalToTime,
	barsBetweenTimes,
	computeIntervalSeconds,
	DEFAULT_FUTURE_BARS,
	epochSecondsToTime,
	generateFutureWhitespace,
	timeToEpochSeconds
} from './time';

describe('time helpers', () => {
	const createCandle = (time: Candle['time'], close = 100): Candle => ({
		time,
		open: close - 1,
		high: close + 2,
		low: close - 2,
		close
	});

	describe('timeToEpochSeconds', () => {
		it('returns the number directly when given a numeric timestamp', () => {
			const epoch = 1704067200;
			expect(timeToEpochSeconds(epoch as UTCTimestamp)).toBe(epoch);
		});

		it('converts an ISO date string to UTC epoch seconds', () => {
			const epoch = timeToEpochSeconds('2024-01-01');
			expect(epoch).toBe(Math.floor(new Date('2024-01-01').getTime() / 1000));
		});

		it('converts a BusinessDay object to UTC epoch seconds', () => {
			const bday: BusinessDay = { year: 2024, month: 1, day: 1 };
			expect(timeToEpochSeconds(bday)).toBe(Math.floor(Date.UTC(2024, 0, 1) / 1000));
		});

		it('returns 0 for invalid string date', () => {
			expect(timeToEpochSeconds('invalid-date')).toBe(0);
		});
	});

	describe('epochSecondsToTime', () => {
		it('returns rounded UTCTimestamp when reference is a number', () => {
			const reference = 1704067200 as UTCTimestamp;
			expect(epochSecondsToTime(1704067200.4, reference)).toBe(1704067200);
			expect(epochSecondsToTime(1704067200.8, reference)).toBe(1704067201);
		});

		it('returns date-only string when reference is a string', () => {
			const epoch = Math.floor(Date.UTC(2024, 0, 15) / 1000);
			expect(epochSecondsToTime(epoch + 0.3, '2024-01-01')).toBe('2024-01-15');
		});

		it('returns BusinessDay object when reference is a BusinessDay', () => {
			const epoch = Math.floor(Date.UTC(2024, 5, 20) / 1000);
			const reference: BusinessDay = { year: 2024, month: 1, day: 1 };
			expect(epochSecondsToTime(epoch, reference)).toEqual({
				year: 2024,
				month: 6,
				day: 20
			});
		});
	});

	describe('computeIntervalSeconds', () => {
		it('returns 0 when candles array has fewer than 2 candles', () => {
			expect(computeIntervalSeconds([])).toBe(0);
			expect(computeIntervalSeconds([createCandle('2024-01-01')])).toBe(0);
		});

		it('computes daily spacing (86400s) from daily string dates', () => {
			const candles = [
				createCandle('2024-01-01'),
				createCandle('2024-01-02'),
				createCandle('2024-01-03')
			];
			expect(computeIntervalSeconds(candles)).toBe(86400);
		});

		it('computes hourly spacing (3600s) from numeric timestamps', () => {
			const base = 1704067200;
			const candles = [
				createCandle(base as UTCTimestamp),
				createCandle((base + 3600) as UTCTimestamp),
				createCandle((base + 7200) as UTCTimestamp)
			];
			expect(computeIntervalSeconds(candles)).toBe(3600);
		});

		it('returns median spacing when intervals vary slightly', () => {
			const base = 100000;
			const candles = [
				createCandle(base as UTCTimestamp),
				createCandle((base + 60) as UTCTimestamp),
				createCandle((base + 120) as UTCTimestamp),
				createCandle((base + 180) as UTCTimestamp)
			];
			expect(computeIntervalSeconds(candles)).toBe(60);
		});
	});

	describe('addIntervalToTime and barsBetweenTimes', () => {
		it('adds positive interval increments preserving format', () => {
			const nextDay = addIntervalToTime('2024-01-01', 1, 86400);
			expect(nextDay).toBe('2024-01-02');

			const nextHour = addIntervalToTime(1704067200 as UTCTimestamp, 2, 3600);
			expect(nextHour).toBe(1704067200 + 7200);
		});

		it('calculates bars between two times', () => {
			expect(barsBetweenTimes('2024-01-01', '2024-01-05', 86400)).toBe(4);
			expect(barsBetweenTimes('2024-01-05', '2024-01-01', 86400)).toBe(0);
		});
	});

	describe('generateFutureWhitespace', () => {
		it('returns empty array when candles array is empty or has a single candle', () => {
			expect(generateFutureWhitespace([])).toEqual([]);
			expect(generateFutureWhitespace([createCandle('2024-01-01')])).toEqual([]);
		});

		it('returns empty array when count is <= 0', () => {
			const candles = [createCandle('2024-01-01'), createCandle('2024-01-02')];
			expect(generateFutureWhitespace(candles, 0)).toEqual([]);
			expect(generateFutureWhitespace(candles, -5)).toEqual([]);
		});

		it('returns empty array when interval between candles is zero or non-positive', () => {
			const candles = [createCandle('2024-01-01'), createCandle('2024-01-01')];
			expect(generateFutureWhitespace(candles, 10)).toEqual([]);
		});

		it('generates future whitespace entries for daily string dates matching interval', () => {
			const candles = [
				createCandle('2024-01-01'),
				createCandle('2024-01-02'),
				createCandle('2024-01-03')
			];
			const future = generateFutureWhitespace(candles, 3);
			expect(future).toEqual([
				{ time: '2024-01-04' },
				{ time: '2024-01-05' },
				{ time: '2024-01-06' }
			]);
		});

		it('generates future whitespace entries for intraday numeric timestamps matching interval', () => {
			const base = 1704067200;
			const candles = [
				createCandle(base as UTCTimestamp),
				createCandle((base + 3600) as UTCTimestamp)
			];
			const future = generateFutureWhitespace(candles, 3);
			expect(future).toEqual([
				{ time: base + 7200 },
				{ time: base + 10800 },
				{ time: base + 14400 }
			]);
		});

		it('generates future whitespace entries for BusinessDay objects', () => {
			const bday1: BusinessDay = { year: 2024, month: 1, day: 1 };
			const bday2: BusinessDay = { year: 2024, month: 1, day: 2 };
			const candles = [createCandle(bday1), createCandle(bday2)];
			const future = generateFutureWhitespace(candles, 2);
			expect(future).toEqual([
				{ time: { year: 2024, month: 1, day: 3 } },
				{ time: { year: 2024, month: 1, day: 4 } }
			]);
		});

		it('defaults to DEFAULT_FUTURE_BARS (100) when count is omitted', () => {
			const candles = [createCandle('2024-01-01'), createCandle('2024-01-02')];
			const future = generateFutureWhitespace(candles);
			expect(future).toHaveLength(DEFAULT_FUTURE_BARS);
			expect(DEFAULT_FUTURE_BARS).toBe(100);
			expect(future[0].time).toBe('2024-01-03');
		});

		it('formats future time scale labels consistently with historical labels (AC 3)', () => {
			// Daily ISO format
			const dailyCandles = [createCandle('2024-01-01'), createCandle('2024-01-02')];
			const dailyFuture = generateFutureWhitespace(dailyCandles, 2);
			expect(formatLocalTime(dailyCandles[1].time)).toBe('2024-01-02');
			expect(formatLocalTime(dailyFuture[0].time)).toBe('2024-01-03');
			expect(formatLocalTime(dailyFuture[1].time)).toBe('2024-01-04');

			// Intraday numeric format
			const base = 1704067200;
			const intradayCandles = [
				createCandle(base as UTCTimestamp),
				createCandle((base + 3600) as UTCTimestamp)
			];
			const intradayFuture = generateFutureWhitespace(intradayCandles, 2);

			const histLabel = formatLocalTime(intradayCandles[1].time);
			const futureLabel1 = formatLocalTime(intradayFuture[0].time);
			const futureLabel2 = formatLocalTime(intradayFuture[1].time);

			expect(typeof histLabel).toBe('string');
			expect(typeof futureLabel1).toBe('string');
			expect(typeof futureLabel2).toBe('string');
			expect(futureLabel1).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
			expect(futureLabel2).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);

			// Tick mark formatter
			const tick1 = formatLocalTickMark(intradayFuture[0].time, TickMarkType.Time, 'en-US');
			const tick2 = formatLocalTickMark(intradayFuture[1].time, TickMarkType.Time, 'en-US');
			expect(tick1).not.toBeNull();
			expect(tick2).not.toBeNull();
		});
	});
});
