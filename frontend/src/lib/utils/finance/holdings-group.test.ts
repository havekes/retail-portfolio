import { describe, it, expect } from 'vitest';
import type { UserHolding } from '$lib/types/account';
import { groupHoldings } from './holdings-group';

function makeHolding(
	overrides: Partial<UserHolding> & Pick<UserHolding, 'id' | 'security_id'>
): UserHolding {
	return {
		security_symbol: 'AAA',
		security_name: 'Alpha Corp',
		quantity: 1,
		average_cost: 100,
		total_value: 100,
		profit_loss: 0,
		currency: 'CAD',
		security_currency: 'CAD',
		unconverted_total_value: 100,
		converted_average_cost: 100,
		converted_latest_price: 100,
		unconverted_profit_loss: 0,
		account_id: 'acc-1',
		account_name: 'Account One',
		...overrides
	};
}

describe('groupHoldings', () => {
	describe("mode: 'company'", () => {
		it('merges the same security held across accounts into one group with summed aggregates', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					quantity: 10,
					converted_average_cost: 150,
					total_value: 2000,
					profit_loss: 500,
					account_id: 'acc-1',
					account_name: 'TFSA'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					quantity: 5,
					converted_average_cost: 180,
					total_value: 1000,
					profit_loss: 100,
					account_id: 'acc-2',
					account_name: 'RRSP'
				})
			];

			const groups = groupHoldings(rows, 'company');

			expect(groups).toHaveLength(1);
			const [group] = groups;
			expect(group.key).toBe('sec-aapl::CAD');
			expect(group.security_symbol).toBe('AAPL');
			expect(group.security_name).toBe('Apple Inc.');
			expect(group.currency).toBe('CAD');
			expect(group.quantity).toBe(15);
			expect(group.total_value).toBe(3000);
			expect(group.profit_loss).toBe(600);
			// Quantity-weighted average of the converted cost: (10*150 + 5*180) / 15.
			expect(group.average_cost).toBeCloseTo(160);
			expect(group.account_count).toBe(2);
			expect(group.rows).toEqual(rows);
		});

		it('keeps groups in first-appearance order and distinct per security', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-msft',
					security_symbol: 'MSFT',
					security_name: 'Microsoft Corp.'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.'
				}),
				makeHolding({
					id: 'h-3',
					security_id: 'sec-msft',
					security_symbol: 'MSFT',
					security_name: 'Microsoft Corp.',
					account_id: 'acc-2'
				})
			];

			const groups = groupHoldings(rows, 'company');

			expect(groups.map((group) => group.key)).toEqual(['sec-msft::CAD', 'sec-aapl::CAD']);
			expect(groups[0].rows.map((row) => row.id)).toEqual(['h-1', 'h-3']);
			expect(groups[1].rows.map((row) => row.id)).toEqual(['h-2']);
		});

		it('separates the same security held in different currencies (no client-side FX)', () => {
			const rows = [
				makeHolding({
					id: 'h-cad',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					currency: 'CAD',
					account_id: 'acc-cad'
				}),
				makeHolding({
					id: 'h-usd',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					currency: 'USD',
					account_id: 'acc-usd'
				})
			];

			const groups = groupHoldings(rows, 'company');

			expect(groups).toHaveLength(2);
			expect(groups.map((group) => group.key)).toEqual(['sec-aapl::CAD', 'sec-aapl::USD']);
			expect(groups.map((group) => group.currency)).toEqual(['CAD', 'USD']);
			expect(groups.map((group) => group.account_count)).toEqual([1, 1]);
		});

		it('is null-safe for profit_loss and average_cost edges', () => {
			const rows = [
				makeHolding({
					id: 'h-null-pl',
					security_id: 'sec-null',
					quantity: 2,
					profit_loss: null,
					converted_average_cost: 10,
					total_value: 20
				}),
				makeHolding({
					id: 'h-null-cost',
					security_id: 'sec-null',
					quantity: 3,
					profit_loss: null,
					converted_average_cost: null,
					total_value: 30
				})
			];

			const [group] = groupHoldings(rows, 'company');

			expect(group.quantity).toBe(5);
			expect(group.total_value).toBe(50);
			// Every row has a null P/L: the group has no meaningful P/L.
			expect(group.profit_loss).toBeNull();
			// Only the non-null converted cost contributes to the weighted average.
			expect(group.average_cost).toBe(10);
		});

		it('sums partial profit_loss values and ignores rows with null costs in the average', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-mix',
					quantity: 4,
					profit_loss: 40,
					converted_average_cost: 25,
					account_id: 'acc-1'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-mix',
					quantity: 6,
					profit_loss: null,
					converted_average_cost: 50,
					account_id: 'acc-1'
				})
			];

			const [group] = groupHoldings(rows, 'company');

			expect(group.profit_loss).toBe(40);
			expect(group.average_cost).toBeCloseTo(40); // (4*25 + 6*50) / 10
			// Two positions, but both belong to the same account.
			expect(group.account_count).toBe(1);
		});

		it('returns an empty array for empty input', () => {
			expect(groupHoldings([], 'company')).toEqual([]);
		});
	});

	describe("mode: 'none'", () => {
		it('returns one group per position in the original order', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					quantity: 10,
					total_value: 2000,
					profit_loss: 500,
					average_cost: 150
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-msft',
					security_symbol: 'MSFT',
					quantity: 5,
					total_value: 1000,
					profit_loss: -100,
					average_cost: 220
				}),
				makeHolding({
					id: 'h-3',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					quantity: 2,
					total_value: 400,
					profit_loss: null,
					average_cost: null,
					account_id: 'acc-2'
				})
			];

			const groups = groupHoldings(rows, 'none');

			expect(groups).toHaveLength(3);
			expect(groups.map((group) => group.key)).toEqual(['h-1', 'h-2', 'h-3']);
			expect(groups.map((group) => group.rows[0].id)).toEqual(['h-1', 'h-2', 'h-3']);
			expect(groups.map((group) => group.security_symbol)).toEqual(['AAPL', 'MSFT', 'AAPL']);
			expect(groups.map((group) => group.account_count)).toEqual([1, 1, 1]);
			expect(groups[0]).toMatchObject({
				quantity: 10,
				total_value: 2000,
				profit_loss: 500,
				average_cost: 150
			});
			expect(groups[2]).toMatchObject({
				quantity: 2,
				total_value: 400,
				profit_loss: null,
				average_cost: null
			});
		});

		it('does not merge the same security held across accounts', () => {
			const rows = [
				makeHolding({ id: 'h-1', security_id: 'sec-aapl', account_id: 'acc-1' }),
				makeHolding({ id: 'h-2', security_id: 'sec-aapl', account_id: 'acc-2' })
			];

			const groups = groupHoldings(rows, 'none');

			expect(groups).toHaveLength(2);
			expect(groups[0].rows).toEqual([rows[0]]);
			expect(groups[1].rows).toEqual([rows[1]]);
		});

		it('returns an empty array for empty input', () => {
			expect(groupHoldings([], 'none')).toEqual([]);
		});
	});
});
