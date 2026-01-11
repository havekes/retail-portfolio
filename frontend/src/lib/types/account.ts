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

export interface AccountTotals {
	cost: Money;
}

export enum AccountType {
	TFSA = 1,
	RRSP = 2,
	FHSA = 3,
	NonRegistered = 4
}

export enum Institution {
	Wealthsimple = 1
}
