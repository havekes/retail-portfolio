import type { Money } from './money';

export interface Account {
	id: string;
	name: string;
	external_id: string;
	account_type_id: AccountType;
	institution_id: Institution;
	currency: string;
	is_active: boolean;
	created_at: Date;
}

export type AccountGroupKeys = 'account_type_id' | 'institution_id';

export interface AccountTotals {
	cost: Money;
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
