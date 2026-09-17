import type { UserHolding } from '$lib/types/account';

export type HoldingsGroupMode = 'none' | 'company';

export type HoldingsGroup = {
	key: string;
	security_name: string;
	security_symbol: string;
	currency: string;
	quantity: number;
	total_value: number;
	profit_loss: number | null;
	average_cost: number | null;
	account_count: number;
	rows: UserHolding[];
};

/**
 * Aggregates user-wide holdings for display.
 *
 * Company grouping keys on `(security_id, currency)` rather than `security_id`
 * alone. The backend converts each holding into its *account's* currency and we
 * deliberately do no client-side FX, so a security held in accounts with
 * different currencies must never be summed together: such a security yields one
 * group per currency (documented compromise — see HOLDINGS-T02 notes).
 *
 * Groups are never reordered: `company` groups follow first appearance and
 * `none` returns one group per position in the original input order.
 */
export function groupHoldings(rows: UserHolding[], mode: HoldingsGroupMode): HoldingsGroup[] {
	if (mode === 'none') {
		return rows.map((row) => ({
			key: row.id,
			security_name: row.security_name,
			security_symbol: row.security_symbol,
			currency: row.currency,
			quantity: row.quantity,
			total_value: row.total_value,
			profit_loss: row.profit_loss,
			average_cost: row.average_cost,
			account_count: 1,
			rows: [row]
		}));
	}

	const groups: HoldingsGroup[] = [];
	const indexByKey = new Map<string, number>();

	for (const row of rows) {
		const key = `${row.security_id}::${row.currency}`;
		let index = indexByKey.get(key);

		if (index === undefined) {
			index = groups.length;
			indexByKey.set(key, index);
			groups.push({
				key,
				security_name: row.security_name,
				security_symbol: row.security_symbol,
				currency: row.currency,
				quantity: 0,
				total_value: 0,
				profit_loss: null,
				average_cost: null,
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
	let profitLoss: number | null = null;
	let weightedCostNumerator = 0;
	let weightedCostQuantity = 0;
	const accountIds = new Set<string>();

	for (const row of group.rows) {
		quantity += row.quantity;
		totalValue += row.total_value;

		if (row.profit_loss !== null && row.profit_loss !== undefined) {
			profitLoss = (profitLoss ?? 0) + row.profit_loss;
		}

		if (row.converted_average_cost !== null && row.converted_average_cost !== undefined) {
			weightedCostNumerator += row.quantity * row.converted_average_cost;
			weightedCostQuantity += row.quantity;
		}

		accountIds.add(row.account_id);
	}

	return {
		...group,
		quantity,
		total_value: totalValue,
		profit_loss: profitLoss,
		average_cost: weightedCostQuantity > 0 ? weightedCostNumerator / weightedCostQuantity : null,
		account_count: accountIds.size
	};
}
