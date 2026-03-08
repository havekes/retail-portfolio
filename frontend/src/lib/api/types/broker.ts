import type { Institution as AccountInstitution } from '@/types/account';

export interface Institution {
	id: string;
	name: string;
	logo: string | null;
	auth_type: string;
	created_at: string;
}

export interface BrokerUser {
	id: string;
	name: string;
	display_name: string | null;
	institution_id: AccountInstitution;
	accounts_synced: number;
	accounts_total: number;
}

export interface ImportBrokerAccountsResponse {
	imported_count: number;
}

export interface BrokerAccount {
	id: string;
	type: string | null;
	display_name: string;
	currency: string;
	external_id?: string;
}

export interface LoginCredentials {
	username: string;
	password?: string;
	otp?: string;
}
