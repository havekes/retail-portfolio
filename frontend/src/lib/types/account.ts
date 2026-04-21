import type { Money } from './money';

export interface Account {
	id: string;
	name: string;
	external_id: string;
	account_type_id: AccountType;
	institution_id: Institution;
	currency: string;
	broker_display_name?: string;
	net_deposits?: number;
	is_active: boolean;
	created_at: Date;
}

export type AccountGroupKeys = 'account_type_id' | 'institution_id';

export interface AccountTotals {
	cost: Money;
	value: Money;
}

export enum AccountType {
	TFSA = 1,
	RRSP = 2,
	FHSA = 3,
	NonRegistered = 4
}

export const getAccountTypeLabel = (
	type: AccountType,
	translate?: (key: string, options?: Record<string, unknown>) => string
): string => {
	if (translate) {
		return translate('account_type_label', { type });
	}

	const labels: Record<AccountType, string> = {
		[AccountType.TFSA]: 'TFSA',
		[AccountType.RRSP]: 'RRSP',
		[AccountType.FHSA]: 'FHSA',
		[AccountType.NonRegistered]: 'Non-Registered'
	};
	return labels[type];
};

export enum Institution {
	Wealthsimple = 1,
	Questrade = 2
}

export const getInstitutionLabel = (
	institution: Institution,
	translate?: (key: string, options?: Record<string, unknown>) => string
): string => {
	if (translate) {
		return translate('institution_label', { institution });
	}

	const labels: Record<Institution, string> = {
		[Institution.Wealthsimple]: 'Wealthsimple',
		[Institution.Questrade]: 'Questrade'
	};
	return labels[institution];
};

export interface Holding {
	id: string;
	security_id: string;
	security_symbol: string;
	security_name: string;
	quantity: number;
	average_cost: number | null;
	total_value: number;
	profit_loss: number | null;
	currency: string;
	security_currency: string;
	unconverted_total_value: number;
	converted_average_cost: number | null;
	converted_latest_price: number | null;
	unconverted_profit_loss: number | null;
	latest_price?: number;
	price_date?: string;
	updated_at?: string;
}

export interface AccountHoldings {
	account_id: string;
	account_name: string;
	holdings: Holding[];
	total_value: number;
	total_profit_loss: number;
	total_profit_loss_percent: number | null;
	net_deposits: number | null;
	currency: string;
}
