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
	describe("mode: 'stock' / 'company'", () => {
		it('merges the same security held across accounts into strictly one group with summed aggregates and combined account names', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					quantity: 10,
					average_cost: 110,
					converted_average_cost: 150,
					total_value: 2000,
					unconverted_total_value: 1500,
					profit_loss: 500,
					unconverted_profit_loss: 375,
					security_currency: 'USD',
					account_id: 'acc-1',
					account_name: 'TFSA'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					quantity: 5,
					average_cost: 140,
					converted_average_cost: 180,
					total_value: 1000,
					unconverted_total_value: 750,
					profit_loss: 100,
					unconverted_profit_loss: 75,
					security_currency: 'USD',
					account_id: 'acc-2',
					account_name: 'RRSP'
				})
			];

			const groups = groupHoldings(rows, 'stock');

			expect(groups).toHaveLength(1);
			const [group] = groups;
			expect(group.id).toBe('sec-aapl');
			expect(group.key).toBe('sec-aapl');
			expect(group.security_id).toBe('sec-aapl');
			expect(group.security_symbol).toBe('AAPL');
			expect(group.security_name).toBe('Apple Inc.');
			expect(group.currency).toBe('CAD');
			expect(group.security_currency).toBe('USD');
			expect(group.quantity).toBe(15);
			expect(group.total_value).toBe(3000);
			expect(group.unconverted_total_value).toBe(2250);
			expect(group.profit_loss).toBe(600);
			expect(group.unconverted_profit_loss).toBe(450);
			// Quantity-weighted average of the converted cost: (10*150 + 5*180) / 15 = 160
			expect(group.converted_average_cost).toBeCloseTo(160);
			// Quantity-weighted average of the native cost: (10*110 + 5*140) / 15 = 120
			expect(group.average_cost).toBeCloseTo(120);
			expect(group.account_names).toEqual(['TFSA', 'RRSP']);
			expect(group.account_count).toBe(2);
			expect(group.rows).toEqual(rows);
		});

		it('supports legacy mode: company identically to stock', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					quantity: 10,
					converted_average_cost: 150,
					total_value: 2000,
					profit_loss: 500
				})
			];

			const groups = groupHoldings(rows, 'company');
			expect(groups).toHaveLength(1);
			expect(groups[0].security_id).toBe('sec-aapl');
		});

		it('keeps groups in first-appearance order and distinct strictly per security_id', () => {
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

			const groups = groupHoldings(rows, 'stock');

			expect(groups.map((group) => group.key)).toEqual(['sec-msft', 'sec-aapl']);
			expect(groups[0].rows.map((row) => row.id)).toEqual(['h-1', 'h-3']);
			expect(groups[1].rows.map((row) => row.id)).toEqual(['h-2']);
		});

		it('merges the same security even if held across different account currencies into strictly one stock row', () => {
			const rows = [
				makeHolding({
					id: 'h-cad',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					currency: 'CAD',
					security_currency: 'USD',
					quantity: 10,
					total_value: 1350,
					unconverted_total_value: 1000,
					account_id: 'acc-cad',
					account_name: 'CAD TFSA'
				}),
				makeHolding({
					id: 'h-usd',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					security_name: 'Apple Inc.',
					currency: 'USD',
					security_currency: 'USD',
					quantity: 5,
					total_value: 675,
					unconverted_total_value: 500,
					account_id: 'acc-usd',
					account_name: 'USD Account'
				})
			];

			const groups = groupHoldings(rows, 'stock');

			expect(groups).toHaveLength(1);
			expect(groups[0].key).toBe('sec-aapl');
			expect(groups[0].currency).toBe('CAD');
			expect(groups[0].security_currency).toBe('USD');
			expect(groups[0].quantity).toBe(15);
			expect(groups[0].total_value).toBe(2025);
			expect(groups[0].unconverted_total_value).toBe(1500);
			expect(groups[0].account_names).toEqual(['CAD TFSA', 'USD Account']);
			expect(groups[0].account_count).toBe(2);
		});

		it('is null-safe for profit_loss and average_cost edges', () => {
			const rows = [
				makeHolding({
					id: 'h-null-pl',
					security_id: 'sec-null',
					quantity: 2,
					profit_loss: null,
					unconverted_profit_loss: null,
					average_cost: 8,
					converted_average_cost: 10,
					total_value: 20
				}),
				makeHolding({
					id: 'h-null-cost',
					security_id: 'sec-null',
					quantity: 3,
					profit_loss: null,
					unconverted_profit_loss: null,
					average_cost: null,
					converted_average_cost: null,
					total_value: 30
				})
			];

			const [group] = groupHoldings(rows, 'stock');

			expect(group.quantity).toBe(5);
			expect(group.total_value).toBe(50);
			// Every row has a null P/L: the group has no meaningful P/L.
			expect(group.profit_loss).toBeNull();
			expect(group.unconverted_profit_loss).toBeNull();
			// Only the non-null costs contribute to the weighted averages.
			expect(group.converted_average_cost).toBe(10);
			expect(group.average_cost).toBe(8);
		});

		it('sums partial profit_loss values and ignores rows with null costs in the average', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-mix',
					quantity: 4,
					profit_loss: 40,
					average_cost: 20,
					converted_average_cost: 25,
					account_id: 'acc-1',
					account_name: 'TFSA'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-mix',
					quantity: 6,
					profit_loss: null,
					average_cost: 40,
					converted_average_cost: 50,
					account_id: 'acc-1',
					account_name: 'TFSA'
				})
			];

			const [group] = groupHoldings(rows, 'stock');

			expect(group.profit_loss).toBe(40);
			expect(group.converted_average_cost).toBeCloseTo(40); // (4*25 + 6*50) / 10
			expect(group.average_cost).toBeCloseTo(32); // (4*20 + 6*40) / 10
			// Two positions, but both belong to the same account.
			expect(group.account_count).toBe(1);
			expect(group.account_names).toEqual(['TFSA']);
		});

		it('returns an empty array for empty input', () => {
			expect(groupHoldings([], 'stock')).toEqual([]);
		});
	});

	describe("mode: 'none'", () => {
		it('returns one group per position in the original order with account_names populated', () => {
			const rows = [
				makeHolding({
					id: 'h-1',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					quantity: 10,
					total_value: 2000,
					profit_loss: 500,
					average_cost: 150,
					account_name: 'TFSA'
				}),
				makeHolding({
					id: 'h-2',
					security_id: 'sec-msft',
					security_symbol: 'MSFT',
					quantity: 5,
					total_value: 1000,
					profit_loss: -100,
					average_cost: 220,
					account_name: 'RRSP'
				}),
				makeHolding({
					id: 'h-3',
					security_id: 'sec-aapl',
					security_symbol: 'AAPL',
					quantity: 2,
					total_value: 400,
					profit_loss: null,
					average_cost: null,
					account_id: 'acc-2',
					account_name: ''
				})
			];

			const groups = groupHoldings(rows, 'none');

			expect(groups).toHaveLength(3);
			expect(groups.map((group) => group.key)).toEqual(['h-1', 'h-2', 'h-3']);
			expect(groups.map((group) => group.id)).toEqual(['h-1', 'h-2', 'h-3']);
			expect(groups.map((group) => group.rows[0].id)).toEqual(['h-1', 'h-2', 'h-3']);
			expect(groups.map((group) => group.security_symbol)).toEqual(['AAPL', 'MSFT', 'AAPL']);
			expect(groups[0].account_names).toEqual(['TFSA']);
			expect(groups[1].account_names).toEqual(['RRSP']);
			expect(groups[2].account_names).toEqual([]);
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
