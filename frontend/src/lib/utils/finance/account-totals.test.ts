import { describe, it, expect } from 'vitest';
import type { AccountTotals } from '$lib/types/account';
import {
	aggregateAccountTotals,
	MIXED_BASIS_LABEL,
	NET_DEPOSITS_BASIS_LABEL,
	type AccountTotalsInput
} from './account-totals';

function makeTotals(overrides: Partial<AccountTotals> = {}): AccountTotals {
	return {
		cost: { value: '0', currencyCode: 'CAD' },
		value: { value: '0', currencyCode: 'CAD' },
		cash: { value: '0', currencyCode: 'CAD' },
		net_deposits: null,
		profit_loss: { value: '0', currencyCode: 'CAD' },
		return_percent: null,
		basis: 'cost',
		...overrides
	};
}

function input(
	accountId: string,
	currency: string,
	value: number,
	profitLoss: number,
	basis: AccountTotals['basis'],
	netDeposits: number | null = null
): AccountTotalsInput {
	return {
		accountId,
		currency,
		totals: makeTotals({
			value: { value: String(value), currencyCode: currency },
			profit_loss: { value: String(profitLoss), currencyCode: currency },
			net_deposits:
				netDeposits == null ? null : { value: String(netDeposits), currencyCode: currency },
			basis
		})
	};
}

describe('aggregateAccountTotals', () => {
	it('returns no buckets for no inputs', () => {
		expect(aggregateAccountTotals([])).toEqual([]);
	});

	it('returns a single account bucket matching its totals, including cash in value', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1234.56, 234.56, 'net_deposits', 1000)
		]);

		expect(buckets).toEqual([
			{
				currency: 'CAD',
				totalValue: 1234.56,
				profitLoss: 234.56,
				returnPercent: 23.456,
				basis: 'net_deposits',
				basisLabel: NET_DEPOSITS_BASIS_LABEL,
				basisAmount: 1000
			}
		]);
	});

	it('sums net deposits into basisAmount for an all-net-deposits bucket', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1000, 100, 'net_deposits', 900),
			input('acc-2', 'CAD', 500, 50, 'net_deposits', 450)
		]);

		expect(buckets[0].basis).toBe('net_deposits');
		expect(buckets[0].basisAmount).toBe(1350);
	});

	it('has no basisAmount on a mixed bucket', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1000, 100, 'net_deposits', 900),
			input('acc-2', 'CAD', 500, 50, 'cost')
		]);

		expect(buckets[0].basis).toBe('mixed');
		expect(buckets[0].basisAmount).toBeNull();
	});

	it('buckets per currency and uses sum(pl)/sum(net_deposits) for an all-net-deposits bucket', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1000, 100, 'net_deposits', 900),
			input('acc-2', 'CAD', 500, 50, 'net_deposits', 450),
			input('acc-3', 'USD', 200, 20, 'cost')
		]);

		expect(buckets).toHaveLength(2);
		const cad = buckets.find((b) => b.currency === 'CAD');
		const usd = buckets.find((b) => b.currency === 'USD');

		expect(cad?.totalValue).toBe(1500);
		expect(cad?.profitLoss).toBe(150);
		// 150 / 1350 * 100
		expect(cad?.returnPercent).toBeCloseTo(11.111, 3);
		expect(cad?.basis).toBe('net_deposits');

		expect(usd?.totalValue).toBe(200);
		expect(usd?.profitLoss).toBe(20);
	});

	it('labels a non-net-deposits bucket "mixed basis" and uses sum(pl)/sum(value - pl)', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1000, 100, 'net_deposits', 900),
			input('acc-2', 'CAD', 500, 50, 'cost')
		]);

		const cad = buckets[0];
		expect(cad.basis).toBe('mixed');
		expect(cad.basisLabel).toBe(MIXED_BASIS_LABEL);
		// denominator = (1000 + 500) - (100 + 50) = 1350
		expect(cad.returnPercent).toBeCloseTo(11.111, 3);
	});

	it('omits the return % when the bucket denominator is zero', () => {
		const allNetDeposits = aggregateAccountTotals([
			input('acc-1', 'CAD', 500, 50, 'net_deposits', 0)
		]);
		expect(allNetDeposits[0].returnPercent).toBeNull();

		const mixed = aggregateAccountTotals([input('acc-2', 'CAD', 500, 500, 'cost')]);
		expect(mixed[0].returnPercent).toBeNull();
	});

	it('treats a missing net_deposits value as zero in an all-net-deposits bucket', () => {
		const buckets = aggregateAccountTotals([
			input('acc-1', 'CAD', 1000, 100, 'net_deposits', 900),
			input('acc-2', 'CAD', 100, 0, 'net_deposits', null)
		]);

		expect(buckets[0].returnPercent).toBeCloseTo((100 / 900) * 100, 6);
	});
});
