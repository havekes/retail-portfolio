import type { Account } from './account';

export interface Portfolio {
	id: string;
	name: string;
	accounts: Account[];
	user_id?: string;
	created_at?: string | null;
	deleted_at?: string | null;
}

export interface PortfolioCreatePayload {
	name: string;
	accounts: string[];
}
