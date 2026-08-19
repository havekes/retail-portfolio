import { describe, it, expect } from 'vitest';
import type { Time } from 'lightweight-charts';
import type { Candle } from './candle';
import {
	calculateSMA,
	calculateEMA,
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

describe('Day-based moving averages (unit: "day")', () => {
	it('calculates smooth rolling SMA on 1h interval (7 bars/day)', () => {
		// 16 hourly candles; with period = 2 days (14 hourly bars), produces 3 points (indices 13, 14, 15)
		const baseTime = 1704067200; // Mon Jan 01 2024 00:00:00 GMT
		const candles: Candle[] = Array.from({ length: 16 }, (_, i) =>
			createCandle((baseTime + i * 3600) as unknown as Time, (i + 1) * 10)
		);

		const result = calculateDayMA(candles, '1h', 2);

		expect(result).toHaveLength(3);
		// index 13: avg(10..140) = (10 + 140) / 2 = 75
		expect(result[0]).toEqual({ time: (baseTime + 13 * 3600) as unknown as Time, value: 75 });
		// index 14: avg(20..150) = (20 + 150) / 2 = 85
		expect(result[1]).toEqual({ time: (baseTime + 14 * 3600) as unknown as Time, value: 85 });
		// index 15: avg(30..160) = (30 + 160) / 2 = 95
		expect(result[2]).toEqual({ time: (baseTime + 15 * 3600) as unknown as Time, value: 95 });

		// Verify continuous rolling transition (no flat steps)
		expect(result[0].value).not.toBe(result[1].value);
		expect(result[1].value).not.toBe(result[2].value);
	});

	it('calculates smooth rolling SMA on 4h interval (2 bars/day)', () => {
		// 6 four-hour candles; with period = 2 days (4 bars), produces 3 points (indices 3, 4, 5)
		const baseTime = 1704067200;
		const candles: Candle[] = Array.from({ length: 6 }, (_, i) =>
			createCandle((baseTime + i * 14400) as unknown as Time, (i + 1) * 10)
		);

		const result = calculateDayMA(candles, '4h', 2);

		expect(result).toHaveLength(3);
		// index 3: avg(10, 20, 30, 40) = 25
		expect(result[0]).toEqual({ time: (baseTime + 3 * 14400) as unknown as Time, value: 25 });
		// index 4: avg(20, 30, 40, 50) = 35
		expect(result[1]).toEqual({ time: (baseTime + 4 * 14400) as unknown as Time, value: 35 });
		// index 5: avg(30, 40, 50, 60) = 45
		expect(result[2]).toEqual({ time: (baseTime + 5 * 14400) as unknown as Time, value: 45 });
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
		// 50-day MA on 1w -> Math.round(50 / 5) = 10 weeks
		const candles: Candle[] = Array.from({ length: 15 }, (_, i) =>
			createCandle(`2024-W${i + 1}`, (i + 1) * 10)
		);

		const result = calculate50DayMA(candles, '1w');
		// 10-period SMA on 15 candles -> 6 values
		expect(result).toHaveLength(6);
		// 10-period SMA for 10..100 -> average is 55
		expect(result[0].value).toBe(55);

		// 200-day MA on 1w -> Math.round(200 / 5) = 40 weeks
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
	it('calculates smooth rolling SMA on 1d interval (5 bars/week)', () => {
		// 12 daily candles; with period = 2 weeks (10 daily bars), produces 3 points (indices 9, 10, 11)
		const candles: Candle[] = Array.from({ length: 12 }, (_, i) =>
			createCandle(`2024-01-${String(i + 1).padStart(2, '0')}`, (i + 1) * 10)
		);

		const result = calculateWeekMA(candles, '1d', 2);

		expect(result).toHaveLength(3);
		// index 9: avg(10..100) = 55
		expect(result[0]).toEqual({ time: '2024-01-10', value: 55 });
		// index 10: avg(20..110) = 65
		expect(result[1]).toEqual({ time: '2024-01-11', value: 65 });
		// index 11: avg(30..120) = 75
		expect(result[2]).toEqual({ time: '2024-01-12', value: 75 });

		// Verify continuous rolling transition (no flat staircase)
		expect(result[0].value).not.toBe(result[1].value);
		expect(result[1].value).not.toBe(result[2].value);
	});

	it('calculates smooth rolling SMA on 1h interval (35 bars/week)', () => {
		// 72 hourly candles; with period = 2 weeks (70 hourly bars), produces 3 points (indices 69, 70, 71)
		const baseTime = 1704067200;
		const candles: Candle[] = Array.from({ length: 72 }, (_, i) =>
			createCandle((baseTime + i * 3600) as unknown as Time, (i + 1) * 10)
		);

		const result = calculateWeekMA(candles, '1h', 2);

		expect(result).toHaveLength(3);
		// index 69: avg(10..700) = 355
		expect(result[0]).toEqual({ time: (baseTime + 69 * 3600) as unknown as Time, value: 355 });
		// index 70: avg(20..710) = 365
		expect(result[1]).toEqual({ time: (baseTime + 70 * 3600) as unknown as Time, value: 365 });
		// index 71: avg(30..720) = 375
		expect(result[2]).toEqual({ time: (baseTime + 71 * 3600) as unknown as Time, value: 375 });
	});

	it('calculates smooth rolling SMA on 4h interval (10 bars/week)', () => {
		// 22 four-hour candles; with period = 2 weeks (20 bars), produces 3 points (indices 19, 20, 21)
		const baseTime = 1704067200;
		const candles: Candle[] = Array.from({ length: 22 }, (_, i) =>
			createCandle((baseTime + i * 14400) as unknown as Time, (i + 1) * 10)
		);

		const result = calculateWeekMA(candles, '4h', 2);

		expect(result).toHaveLength(3);
		// index 19: avg(10..200) = 105
		expect(result[0]).toEqual({ time: (baseTime + 19 * 14400) as unknown as Time, value: 105 });
		// index 20: avg(20..210) = 115
		expect(result[1]).toEqual({ time: (baseTime + 20 * 14400) as unknown as Time, value: 115 });
		// index 21: avg(30..220) = 125
		expect(result[2]).toEqual({ time: (baseTime + 21 * 14400) as unknown as Time, value: 125 });
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

		const result = calculateDayMA(candles, '1d', 2);
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
	it('returns empty array when candle series has fewer candles than effective period', () => {
		// 30 candles of 1h data
		const candles: Candle[] = Array.from({ length: 30 }, (_, i) => {
			const d = Math.floor(new Date(2024, 0, i + 1, 10, 0).getTime() / 1000);
			return createCandle(d as unknown as Time, 100);
		});

		// 50-day MA on 1h requires 50 * 7 = 350 candles
		expect(calculate50DayMA(candles, '1h')).toEqual([]);
		// 50-week MA on 1d requires 50 * 5 = 250 candles
		expect(calculate50WeekMA(candles, '1d')).toEqual([]);
		// 50-week MA on 1h requires 50 * 35 = 1750 candles
		expect(calculate50WeekMA(candles, '1h')).toEqual([]);
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

	it('falls back to exact period for unrecognized interval', () => {
		const candles: Candle[] = [
			createCandle('2024-01-01', 10),
			createCandle('2024-01-02', 20),
			createCandle('2024-01-03', 30)
		];

		const result = calculateTimeframeMA(candles, { interval: 'unknown', period: 2, unit: 'day' });
		expect(result).toEqual([
			{ time: '2024-01-02', value: 15 },
			{ time: '2024-01-03', value: 25 }
		]);
	});
});
