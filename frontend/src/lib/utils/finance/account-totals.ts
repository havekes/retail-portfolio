import type { AccountTotals } from '$lib/types/account';
import { moneyToNumber } from '$lib/types/money';

/** One account's server-computed performance, tagged with its owning currency. */
export interface AccountTotalsInput {
	accountId: string;
	currency: string;
	totals: AccountTotals;
}

/** How the bucket's return % denominator was chosen. */
export type TotalsBasis = 'net_deposits' | 'mixed';

export interface CurrencyTotalsBucket {
	currency: string;
	totalValue: number;
	profitLoss: number;
	returnPercent: number | null;
	basis: TotalsBasis;
	basisLabel: string;
	/**
	 * Sum of the bucket's `net_deposits` when every account reports that basis,
	 * otherwise `null` (a mixed bucket has no single basis amount to show).
	 */
	basisAmount: number | null;
}

export const NET_DEPOSITS_BASIS_LABEL = 'net deposits basis';
export const MIXED_BASIS_LABEL = 'mixed basis';

/**
 * Sum per-account performance into one bucket per currency.
 *
 * Currencies are never summed together (the backend converts each account into
 * its own currency). Return % is only aggregated when every account in the
 * bucket reports a `net_deposits` basis — `sum(profit_loss) / sum(net_deposits)`;
 * any other mix falls back to `sum(profit_loss) / sum(value - profit_loss)` and
 * is labelled "mixed basis".
 */
export function aggregateAccountTotals(inputs: AccountTotalsInput[]): CurrencyTotalsBucket[] {
	const buckets = new Map<string, AccountTotalsInput[]>();

	for (const input of inputs) {
		const existing = buckets.get(input.currency);
		if (existing) {
			existing.push(input);
		} else {
			buckets.set(input.currency, [input]);
		}
	}

	return Array.from(buckets, ([currency, group]) => {
		let totalValue = 0;
		let profitLoss = 0;
		let netDeposits = 0;
		let allNetDeposits = true;

		for (const { totals } of group) {
			totalValue += moneyToNumber(totals.value);
			profitLoss += moneyToNumber(totals.profit_loss);
			if (totals.basis !== 'net_deposits') {
				allNetDeposits = false;
			}
			netDeposits += totals.net_deposits ? moneyToNumber(totals.net_deposits) : 0;
		}

		const denominator = allNetDeposits ? netDeposits : totalValue - profitLoss;
		const returnPercent = denominator !== 0 ? (profitLoss / denominator) * 100 : null;

		return {
			currency,
			totalValue,
			profitLoss,
			returnPercent,
			basis: allNetDeposits ? 'net_deposits' : 'mixed',
			basisLabel: allNetDeposits ? NET_DEPOSITS_BASIS_LABEL : MIXED_BASIS_LABEL,
			basisAmount: allNetDeposits ? netDeposits : null
		};
	});
}
