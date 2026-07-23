import type { Account } from './account';

export interface Portfolio {
	id: string;
	name: string;
	accounts: Account[];
}

export interface PortfolioCreatePayload {
	name: string;
	accounts: string[];
}
