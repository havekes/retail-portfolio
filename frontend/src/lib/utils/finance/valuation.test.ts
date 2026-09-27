import { describe, it, expect } from 'vitest';
import { formatValuationRange } from './valuation';

describe('formatValuationRange', () => {
	it('formats standard ranges with 2 decimal places and en dash', () => {
		expect(formatValuationRange(20, 50)).toBe('20.00 – 50.00');
		expect(formatValuationRange(20.5, 50.125)).toBe('20.50 – 50.13');
		expect(formatValuationRange(0, 10)).toBe('0.00 – 10.00');
	});

	it('formats large numbers with commas', () => {
		expect(formatValuationRange(1200, 2500)).toBe('1,200.00 – 2,500.00');
		expect(formatValuationRange(1000000, 2500000)).toBe('1,000,000.00 – 2,500,000.00');
	});

	it('returns em dash ("—") when either bound is null or undefined', () => {
		expect(formatValuationRange(null, 50)).toBe('—');
		expect(formatValuationRange(20, null)).toBe('—');
		expect(formatValuationRange(undefined, 50)).toBe('—');
		expect(formatValuationRange(20, undefined)).toBe('—');
		expect(formatValuationRange(null, null)).toBe('—');
		expect(formatValuationRange(undefined, undefined)).toBe('—');
		expect(formatValuationRange()).toBe('—');
	});

	it('returns em dash ("—") when either bound is NaN or Infinity', () => {
		expect(formatValuationRange(NaN, 50)).toBe('—');
		expect(formatValuationRange(20, NaN)).toBe('—');
		expect(formatValuationRange(Infinity, 50)).toBe('—');
		expect(formatValuationRange(20, Infinity)).toBe('—');
		expect(formatValuationRange(-Infinity, 50)).toBe('—');
	});
});
