import { describe, it, expect } from 'vitest';
import type { Time } from 'lightweight-charts';
import type { Candle } from './candle';
import {
	calculateSMA,
	calculateEMA,
	getDayKey,
	getWeekKey,
	calculateTimeframeMA,
	calculateDayMA,
	calculateWeekMA,
	calculate50DayMA,
	calculate200DayMA,
	calculate50WeekMA,
	calculate200WeekMA
} from './moving-average';

function createCandle(time: Time, close: number, open = close, high = close, low = close): Candle {
	return { time, open, high, low, close };
}

describe('calculateSMA & calculateEMA (backward compatibility)', () => {
	it('calculates simple moving average correctly', () => {
		const candles: Candle[] = [
			createCandle('2024-01-01', 10),
			createCandle('2024-01-02', 20),
			createCandle('2024-01-03', 30),
			createCandle('2024-01-04', 40),
			createCandle('2024-01-05', 50)
		];

		const sma = calculateSMA(candles, 3);
		expect(sma).toEqual([
			{ time: '2024-01-03', value: 20 },
			{ time: '2024-01-04', value: 30 },
			{ time: '2024-01-05', value: 40 }
		]);
	});

	it('returns empty array when candle count is less than period or period is invalid', () => {
		const candles: Candle[] = [createCandle('2024-01-01', 10)];
		expect(calculateSMA(candles, 5)).toEqual([]);
		expect(calculateSMA([], 3)).toEqual([]);
		expect(calculateSMA(candles, 0)).toEqual([]);
		expect(calculateSMA(candles, -1)).toEqual([]);
	});

	it('calculates exponential moving average correctly', () => {
		const candles: Candle[] = [
			createCandle('2024-01-01', 10),
			createCandle('2024-01-02', 20),
			createCandle('2024-01-03', 30),
			createCandle('2024-01-04', 40)
		];

		const ema = calculateEMA(candles, 2);
		expect(ema.length).toBe(4);
		// Period 2: first EMA at index 1 is (10 + 20) / 2 = 15
		// Multiplier = 2 / (2 + 1) = 2/3
		// index 2: (30 - 15) * (2/3) + 15 = 25
		// index 3: (40 - 25) * (2/3) + 25 = 35
		expect(ema[0]).toBeUndefined();
		expect(ema[1]).toBeCloseTo(15);
		expect(ema[2]).toBeCloseTo(25);
		expect(ema[3]).toBeCloseTo(35);
	});

	it('returns empty array for calculateEMA with invalid period or insufficient data', () => {
		expect(calculateEMA([], 3)).toEqual([]);
		expect(calculateEMA([createCandle('2024-01-01', 10)], 3)).toEqual([]);
		expect(calculateEMA([createCandle('2024-01-01', 10)], 0)).toEqual([]);
	});
});

describe('getDayKey & getWeekKey helpers', () => {
	it('extracts day keys consistently across timestamp types', () => {
		// String date
		expect(getDayKey(new Date(2024, 0, 15))).toBe('2024-01-15');
		// Month padding
		expect(getDayKey(new Date(2024, 8, 5))).toBe('2024-09-05');
	});

	it('extracts Monday-anchored ISO week keys across all days of the week', () => {
		// Monday Jan 15, 2024
		expect(getWeekKey(new Date(2024, 0, 15))).toBe('2024-01-15');
		// Tuesday Jan 16, 2024
		expect(getWeekKey(new Date(2024, 0, 16))).toBe('2024-01-15');
		// Wednesday Jan 17, 2024
		expect(getWeekKey(new Date(2024, 0, 17))).toBe('2024-01-15');
		// Friday Jan 19, 2024
		expect(getWeekKey(new Date(2024, 0, 19))).toBe('2024-01-15');
		// Saturday Jan 20, 2024
		expect(getWeekKey(new Date(2024, 0, 20))).toBe('2024-01-15');
		// Sunday Jan 21, 2024 (belongs to week of Mon Jan 15)
		expect(getWeekKey(new Date(2024, 0, 21))).toBe('2024-01-15');
		// Following Monday Jan 22, 2024
		expect(getWeekKey(new Date(2024, 0, 22))).toBe('2024-01-22');
	});

	it('handles year boundary week calculations correctly', () => {
		// Sunday Dec 31, 2023 -> belongs to Monday Dec 25, 2023
		expect(getWeekKey(new Date(2023, 11, 31))).toBe('2023-12-25');
		// Monday Jan 1, 2024 -> belongs to Monday Jan 1, 2024
		expect(getWeekKey(new Date(2024, 0, 1))).toBe('2024-01-01');
	});
});

describe('Day-based moving averages (unit: "day")', () => {
	it('projects daily MA onto intraday 1h candles with Unix second timestamps', () => {
		// 3 days of 1h data, 3 bars per day (e.g. 10:00, 11:00, 12:00)
		// Day 1: 2024-01-15 (closes: 10, 12, 14 -> daily close = 14)
		// Day 2: 2024-01-16 (closes: 20, 22, 24 -> daily close = 24)
		// Day 3: 2024-01-17 (closes: 30, 32, 34 -> daily close = 34)
		const d1_base = Math.floor(new Date(2024, 0, 15, 10, 0, 0).getTime() / 1000);
		const d2_base = Math.floor(new Date(2024, 0, 16, 10, 0, 0).getTime() / 1000);
		const d3_base = Math.floor(new Date(2024, 0, 17, 10, 0, 0).getTime() / 1000);

		const candles: Candle[] = [
			createCandle(d1_base as unknown as Time, 10),
			createCandle((d1_base + 3600) as unknown as Time, 12),
			createCandle((d1_base + 7200) as unknown as Time, 14),

			createCandle(d2_base as unknown as Time, 20),
			createCandle((d2_base + 3600) as unknown as Time, 22),
			createCandle((d2_base + 7200) as unknown as Time, 24),

			createCandle(d3_base as unknown as Time, 30),
			createCandle((d3_base + 3600) as unknown as Time, 32),
			createCandle((d3_base + 7200) as unknown as Time, 34)
		];

		// 2-day MA on 1h interval
		const result = calculateDayMA(candles, '1h', 2);

		// Day 1: (only 1 day of history) -> omitted
		// Day 2: (14 + 24) / 2 = 19 -> projected onto all 3 candles of Day 2
		// Day 3: (24 + 34) / 2 = 29 -> projected onto all 3 candles of Day 3
		expect(result).toHaveLength(6);

		expect(result[0]).toEqual({ time: d2_base as unknown as Time, value: 19 });
		expect(result[1]).toEqual({ time: (d2_base + 3600) as unknown as Time, value: 19 });
		expect(result[2]).toEqual({ time: (d2_base + 7200) as unknown as Time, value: 19 });

		expect(result[3]).toEqual({ time: d3_base as unknown as Time, value: 29 });
		expect(result[4]).toEqual({ time: (d3_base + 3600) as unknown as Time, value: 29 });
		expect(result[5]).toEqual({ time: (d3_base + 7200) as unknown as Time, value: 29 });
	});

	it('projects daily MA onto intraday 4h candles', () => {
		const d1_base = Math.floor(new Date(2024, 0, 15, 9, 30, 0).getTime() / 1000);
		const d2_base = Math.floor(new Date(2024, 0, 16, 9, 30, 0).getTime() / 1000);

		const candles: Candle[] = [
			createCandle(d1_base as unknown as Time, 100),
			createCandle((d1_base + 14400) as unknown as Time, 110),
			createCandle(d2_base as unknown as Time, 120),
			createCandle((d2_base + 14400) as unknown as Time, 130)
		];

		const result = calculateDayMA(candles, '4h', 2);
		// Daily closes: Day 1 = 110, Day 2 = 130 -> 2-day MA = 120
		expect(result).toHaveLength(2);
		expect(result[0]).toEqual({ time: d2_base as unknown as Time, value: 120 });
		expect(result[1]).toEqual({ time: (d2_base + 14400) as unknown as Time, value: 120 });
	});

	it('computes standard SMA on 1d series', () => {
		const candles: Candle[] = Array.from({ length: 60 }, (_, i) => {
			const day = String(i + 1).padStart(2, '0');
			return createCandle(`2024-01-${day}`, (i + 1) * 10);
		});

		const result50 = calculate50DayMA(candles, '1d');
		expect(result50).toHaveLength(11);
		// 50th day (index 49) average of 10..500 = (10 + 500) / 2 = 255
		expect(result50[0].value).toBe(255);
		expect(result50[0].time).toBe('2024-01-50');
	});

	it('scales period appropriately for 1w series (period / 5)', () => {
		// 50-day MA on 1w -> 10 weeks
		const candles: Candle[] = Array.from({ length: 15 }, (_, i) =>
			createCandle(`2024-W${i + 1}`, (i + 1) * 10)
		);

		const result = calculate50DayMA(candles, '1w');
		// 50 / 5 = 10 period SMA on 15 candles -> 6 values
		expect(result).toHaveLength(6);
		// 10-period SMA for 10..100 -> average is 55
		expect(result[0].value).toBe(55);

		// 200-day MA on 1w -> 40 weeks
		const candles200: Candle[] = Array.from({ length: 45 }, (_, i) =>
			createCandle(`2024-W${i + 1}`, 100)
		);
		const result200 = calculate200DayMA(candles200, '1w');
		expect(result200).toHaveLength(6); // 45 - 40 + 1
		expect(result200[0].value).toBe(100);
	});

	it('scales period appropriately for 1m series (period / 21)', () => {
		// 50-day MA on 1m -> Math.round(50 / 21) = 2 months
		const candles: Candle[] = [
			createCandle('2024-01-01', 10),
			createCandle('2024-02-01', 20),
			createCandle('2024-03-01', 30)
		];

		const result50 = calculate50DayMA(candles, '1m');
		expect(result50).toEqual([
			{ time: '2024-02-01', value: 15 },
			{ time: '2024-03-01', value: 25 }
		]);

		// 200-day MA on 1m -> Math.round(200 / 21) = 10 months
		const candles200: Candle[] = Array.from({ length: 12 }, (_, i) =>
			createCandle(`2024-${String(i + 1).padStart(2, '0')}-01`, 50)
		);
		const result200 = calculate200DayMA(candles200, '1m');
		expect(result200).toHaveLength(3); // 12 - 10 + 1
		expect(result200[0].value).toBe(50);
	});
});

describe('Week-based moving averages (unit: "week")', () => {
	it('groups daily 1d candles by week and projects weekly MA onto daily candles', () => {
		// 3 weeks of daily trading days (Mon-Fri)
		// Week 1 (Jan 15 - Jan 19): daily closes 10, 11, 12, 13, 14 -> weekly close = 14
		// Week 2 (Jan 22 - Jan 26): daily closes 20, 21, 22, 23, 24 -> weekly close = 24
		// Week 3 (Jan 29 - Feb 02): daily closes 30, 31, 32, 33, 34 -> weekly close = 34
		const candles: Candle[] = [
			// Week 1
			createCandle('2024-01-15', 10),
			createCandle('2024-01-16', 11),
			createCandle('2024-01-17', 12),
			createCandle('2024-01-18', 13),
			createCandle('2024-01-19', 14),
			// Week 2
			createCandle('2024-01-22', 20),
			createCandle('2024-01-23', 21),
			createCandle('2024-01-24', 22),
			createCandle('2024-01-25', 23),
			createCandle('2024-01-26', 24),
			// Week 3
			createCandle('2024-01-29', 30),
			createCandle('2024-01-30', 31),
			createCandle('2024-01-31', 32),
			createCandle('2024-02-01', 33),
			createCandle('2024-02-02', 34)
		];

		// 2-week MA on 1d interval
		const result = calculateWeekMA(candles, '1d', 2);

		// Week 1: omitted
		// Week 2: (14 + 24) / 2 = 19 -> projected onto all 5 days of Week 2
		// Week 3: (24 + 34) / 2 = 29 -> projected onto all 5 days of Week 3
		expect(result).toHaveLength(10);
		expect(result.slice(0, 5).every((pt) => pt.value === 19)).toBe(true);
		expect(result.slice(5, 10).every((pt) => pt.value === 29)).toBe(true);
		expect(result[0].time).toBe('2024-01-22');
		expect(result[4].time).toBe('2024-01-26');
		expect(result[5].time).toBe('2024-01-29');
		expect(result[9].time).toBe('2024-02-02');
	});

	it('groups intraday 1h candles by week and projects weekly MA onto intraday bars', () => {
		// Week 1 (Mon Jan 15): 2 bars, close of last bar = 50
		// Week 2 (Mon Jan 22): 2 bars, close of last bar = 70
		const w1_t1 = Math.floor(new Date(2024, 0, 15, 10, 0).getTime() / 1000);
		const w1_t2 = Math.floor(new Date(2024, 0, 15, 11, 0).getTime() / 1000);
		const w2_t1 = Math.floor(new Date(2024, 0, 22, 10, 0).getTime() / 1000);
		const w2_t2 = Math.floor(new Date(2024, 0, 22, 11, 0).getTime() / 1000);

		const candles: Candle[] = [
			createCandle(w1_t1 as unknown as Time, 40),
			createCandle(w1_t2 as unknown as Time, 50),
			createCandle(w2_t1 as unknown as Time, 60),
			createCandle(w2_t2 as unknown as Time, 70)
		];

		const result = calculateWeekMA(candles, '1h', 2);
		// 2-week MA: Week 1 close = 50, Week 2 close = 70 -> MA = 60
		expect(result).toHaveLength(2);
		expect(result[0]).toEqual({ time: w2_t1 as unknown as Time, value: 60 });
		expect(result[1]).toEqual({ time: w2_t2 as unknown as Time, value: 60 });
	});

	it('computes standard SMA on 1w series for 50-week and 200-week MAs', () => {
		const candles: Candle[] = Array.from({ length: 60 }, (_, i) =>
			createCandle(`2024-W${i + 1}`, (i + 1) * 2)
		);

		const result50 = calculate50WeekMA(candles, '1w');
		expect(result50).toHaveLength(11);
		// 50-period SMA for 2..100 -> average is 51
		expect(result50[0].value).toBe(51);

		const candles200: Candle[] = Array.from({ length: 210 }, (_, i) =>
			createCandle(`2020-W${i + 1}`, 100)
		);
		const result200 = calculate200WeekMA(candles200, '1w');
		expect(result200).toHaveLength(11);
		expect(result200[0].value).toBe(100);
	});

	it('scales period appropriately for 1m series (period * 12 / 52)', () => {
		// 50-week MA on 1m -> Math.round(50 * 12 / 52) = Math.round(11.538) = 12 months
		const candles50: Candle[] = Array.from({ length: 15 }, (_, i) =>
			createCandle(`2024-${String(i + 1).padStart(2, '0')}-01`, 100)
		);
		const result50 = calculate50WeekMA(candles50, '1m');
		expect(result50).toHaveLength(4); // 15 - 12 + 1
		expect(result50[0].value).toBe(100);

		// 200-week MA on 1m -> Math.round(200 * 12 / 52) = Math.round(46.15) = 46 months
		const candles200: Candle[] = Array.from({ length: 50 }, (_, i) =>
			createCandle(`2020-${String(i + 1).padStart(2, '0')}-01`, 200)
		);
		const result200 = calculate200WeekMA(candles200, '1m');
		expect(result200).toHaveLength(5); // 50 - 46 + 1
		expect(result200[0].value).toBe(200);
	});
});

describe('Lightweight Charts Time format support', () => {
	it('handles BusinessDay objects in calculateTimeframeMA', () => {
		const candles: Candle[] = [
			createCandle({ year: 2024, month: 1, day: 15 } as unknown as Time, 10),
			createCandle({ year: 2024, month: 1, day: 16 } as unknown as Time, 20),
			createCandle({ year: 2024, month: 1, day: 17 } as unknown as Time, 30)
		];

		const result = calculateDayMA(candles, '1h', 2);
		expect(result).toHaveLength(2);
		expect(result[0]).toEqual({
			time: { year: 2024, month: 1, day: 16 } as unknown as Time,
			value: 15
		});
		expect(result[1]).toEqual({
			time: { year: 2024, month: 1, day: 17 } as unknown as Time,
			value: 25
		});
	});
});

describe('Edge cases and error handling', () => {
	it('returns empty array when candle series has fewer unique days/weeks than required period', () => {
		// 30 days of 1h data
		const candles: Candle[] = Array.from({ length: 30 }, (_, i) => {
			const d = Math.floor(new Date(2024, 0, i + 1, 10, 0).getTime() / 1000);
			return createCandle(d as unknown as Time, 100);
		});

		// 50-day MA requires 50 distinct days
		expect(calculate50DayMA(candles, '1h')).toEqual([]);
		// 50-week MA requires 50 distinct weeks
		expect(calculate50WeekMA(candles, '1d')).toEqual([]);
	});

	it('returns empty array on empty candles or invalid options', () => {
		expect(calculateTimeframeMA([], { interval: '1d', period: 50 })).toEqual([]);
		expect(
			calculateTimeframeMA([createCandle('2024-01-01', 10)], { interval: '1d', period: 0 })
		).toEqual([]);
		expect(
			calculateTimeframeMA([createCandle('2024-01-01', 10)], { interval: '1d', period: -5 })
		).toEqual([]);
	});

	it('correctly groups across holiday-shortened weeks', () => {
		// Week 1: Only Mon and Tue (holiday Wed-Fri), closes = 10, 20 -> weekly close = 20
		// Week 2: Only Mon (holiday Tue-Fri), closes = 40 -> weekly close = 40
		const candles: Candle[] = [
			createCandle('2024-01-15', 10), // Mon
			createCandle('2024-01-16', 20), // Tue
			createCandle('2024-01-22', 40) // Mon (Week 2)
		];

		const result = calculateWeekMA(candles, '1d', 2);
		// 2-week MA: (20 + 40) / 2 = 30 for Week 2
		expect(result).toEqual([{ time: '2024-01-22', value: 30 }]);
	});
});
