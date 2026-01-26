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

// Add method to compute label here using translations
// (account_type: AccountType) => {
// 	return $t('account_type_label', { type: account_type });
// };

export enum Institution {
	Wealthsimple = 1
}
