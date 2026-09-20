import type { UserHolding } from '$lib/types/account';

export type HoldingsGroupMode = 'none' | 'stock' | 'company';

export type HoldingsGroup = {
	id: string;
	key: string;
	security_id: string;
	security_name: string;
	security_symbol: string;
	currency: string;
	security_currency: string;
	quantity: number;
	total_value: number;
	unconverted_total_value: number;
	profit_loss: number | null;
	unconverted_profit_loss: number | null;
	average_cost: number | null;
	converted_average_cost: number | null;
	latest_price?: number;
	price_date?: string;
	account_names: string[];
	account_count: number;
	rows: UserHolding[];
};

/**
 * Aggregates user-wide holdings for display.
 *
 * Stock grouping keys on `security_id` (strictly one group per stock across all accounts).
 * Quantities, CAD total values, native unconverted values, and profit/loss
 * are summed across accounts, and weighted average costs are computed.
 *
 * Groups are never reordered: stock groups follow first appearance and
 * `none` returns one group per position in the original input order.
 */
export function groupHoldings(rows: UserHolding[], mode: HoldingsGroupMode): HoldingsGroup[] {
	if (mode === 'none') {
		return rows.map((row) => ({
			id: row.id,
			key: row.id,
			security_id: row.security_id,
			security_name: row.security_name,
			security_symbol: row.security_symbol,
			currency: row.currency,
			security_currency: row.security_currency,
			quantity: row.quantity,
			total_value: row.total_value,
			unconverted_total_value: row.unconverted_total_value ?? row.total_value,
			profit_loss: row.profit_loss,
			unconverted_profit_loss: row.unconverted_profit_loss,
			average_cost: row.average_cost,
			converted_average_cost: row.converted_average_cost,
			latest_price: row.latest_price,
			price_date: row.price_date,
			account_names: row.account_name ? [row.account_name] : [],
			account_count: 1,
			rows: [row]
		}));
	}

	const groups: HoldingsGroup[] = [];
	const indexByKey = new Map<string, number>();

	for (const row of rows) {
		const key = row.security_id;
		let index = indexByKey.get(key);

		if (index === undefined) {
			index = groups.length;
			indexByKey.set(key, index);
			groups.push({
				id: row.security_id,
				key,
				security_id: row.security_id,
				security_name: row.security_name,
				security_symbol: row.security_symbol,
				currency: 'CAD',
				security_currency: row.security_currency,
				quantity: 0,
				total_value: 0,
				unconverted_total_value: 0,
				profit_loss: null,
				unconverted_profit_loss: null,
				average_cost: null,
				converted_average_cost: null,
				latest_price: row.latest_price,
				price_date: row.price_date,
				account_names: [],
				account_count: 0,
				rows: []
			});
		}

		groups[index].rows.push(row);
	}

	return groups.map(aggregateGroup);
}

function aggregateGroup(group: HoldingsGroup): HoldingsGroup {
	let quantity = 0;
	let totalValue = 0;
	let unconvertedTotalValue = 0;
	let profitLoss: number | null = null;
	let unconvertedProfitLoss: number | null = null;
	let cadCostNumerator = 0;
	let cadCostQuantity = 0;
	let nativeCostNumerator = 0;
	let nativeCostQuantity = 0;
	const accountIds = new Set<string>();
	const accountNames: string[] = [];

	for (const row of group.rows) {
		quantity += row.quantity;
		totalValue += row.total_value;
		unconvertedTotalValue += row.unconverted_total_value ?? row.total_value;

		if (row.profit_loss !== null && row.profit_loss !== undefined) {
			profitLoss = (profitLoss ?? 0) + row.profit_loss;
		}

		if (row.unconverted_profit_loss !== null && row.unconverted_profit_loss !== undefined) {
			unconvertedProfitLoss = (unconvertedProfitLoss ?? 0) + row.unconverted_profit_loss;
		}

		if (row.converted_average_cost !== null && row.converted_average_cost !== undefined) {
			cadCostNumerator += row.quantity * row.converted_average_cost;
			cadCostQuantity += row.quantity;
		}

		if (row.average_cost !== null && row.average_cost !== undefined) {
			nativeCostNumerator += row.quantity * row.average_cost;
			nativeCostQuantity += row.quantity;
		}

		if (row.account_id) {
			accountIds.add(row.account_id);
		}

		if (row.account_name && row.account_name.trim().length > 0) {
			const name = row.account_name.trim();
			if (!accountNames.includes(name)) {
				accountNames.push(name);
			}
		}
	}

	const firstRow = group.rows[0];

	return {
		...group,
		quantity,
		total_value: totalValue,
		unconverted_total_value: unconvertedTotalValue,
		profit_loss: profitLoss,
		unconverted_profit_loss: unconvertedProfitLoss,
		average_cost: nativeCostQuantity > 0 ? nativeCostNumerator / nativeCostQuantity : null,
		converted_average_cost: cadCostQuantity > 0 ? cadCostNumerator / cadCostQuantity : null,
		currency: 'CAD',
		security_currency: firstRow?.security_currency ?? group.security_currency ?? 'CAD',
		latest_price: firstRow?.latest_price,
		price_date: firstRow?.price_date,
		account_names: accountNames,
		account_count: accountIds.size
	};
}
