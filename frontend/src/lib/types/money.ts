export interface Money {
	value: string;
	units: number;
	nanos: number;
	currencyCode: string;
}

export const money = (money: Money): string => {
	const amount = Number(money.units + money.nanos / 1000000000);
	return `$${amount.toLocaleString()}`;
};
