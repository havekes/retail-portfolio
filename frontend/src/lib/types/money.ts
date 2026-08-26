export interface Money {
	value?: string;
	units?: number;
	nanos?: number;
	currencyCode?: string;
}

export function moneyToNumber(m?: Money | null): number {
	if (!m) return 0;
	if (typeof m.units === 'number') {
		return m.units + (m.nanos ? m.nanos / 1_000_000_000 : 0);
	}
	if (typeof m.value === 'string') {
		return parseFloat(m.value) || 0;
	}
	return 0;
}

export const money = (money: Money): string => {
	const amount = moneyToNumber(money);
	return `$${amount.toLocaleString()}`;
};
