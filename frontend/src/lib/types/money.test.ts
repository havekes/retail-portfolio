import { describe, it, expect } from 'vitest';
import { money, moneyToNumber, type Money } from './money';

describe('moneyToNumber', () => {
	it('returns 0 for undefined or null input', () => {
		expect(moneyToNumber(undefined)).toBe(0);
		expect(moneyToNumber(null)).toBe(0);
		expect(moneyToNumber()).toBe(0);
	});

	it('returns 0 for an empty object', () => {
		expect(moneyToNumber({})).toBe(0);
	});

	it('calculates value from units when nanos is missing or zero', () => {
		expect(moneyToNumber({ units: 100 })).toBe(100);
		expect(moneyToNumber({ units: 100, nanos: 0 })).toBe(100);
	});

	it('calculates value from units and nanos correctly', () => {
		expect(moneyToNumber({ units: 10, nanos: 500_000_000 })).toBe(10.5);
		expect(moneyToNumber({ units: 0, nanos: 750_000_000 })).toBe(0.75);
	});

	it('calculates negative units and nanos correctly', () => {
		expect(moneyToNumber({ units: -10, nanos: -500_000_000 })).toBe(-10.5);
	});

	it('falls back to value string if units is not a number', () => {
		expect(moneyToNumber({ value: '123.45' })).toBe(123.45);
		expect(moneyToNumber({ value: '0' })).toBe(0);
		expect(moneyToNumber({ value: '-50.25' })).toBe(-50.25);
	});

	it('falls back to 0 if value string cannot be parsed as a number', () => {
		expect(moneyToNumber({ value: 'not-a-number' })).toBe(0);
		expect(moneyToNumber({ value: '' })).toBe(0);
	});

	it('prioritizes units over value string if units is provided', () => {
		expect(moneyToNumber({ units: 50, nanos: 0, value: '999' })).toBe(50);
	});

	it('returns 0 if neither units nor value is present', () => {
		expect(moneyToNumber({ currencyCode: 'USD' })).toBe(0);
	});
});

describe('money', () => {
	it('formats money with units and nanos', () => {
		const m: Money = { units: 1500, nanos: 0, currencyCode: 'USD', value: '1500' };
		expect(money(m)).toBe('$1,500');
	});

	it('formats money with fractional values', () => {
		const m: Money = { units: 10, nanos: 500_000_000 };
		expect(money(m)).toBe('$10.5');
	});

	it('formats money using value string fallback', () => {
		const m: Money = { value: '2500' };
		expect(money(m)).toBe('$2,500');
	});

	it('formats zero money as $0', () => {
		const m: Money = { units: 0, nanos: 0 };
		expect(money(m)).toBe('$0');
	});
});
