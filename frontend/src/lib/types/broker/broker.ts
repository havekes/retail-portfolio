import { Institution } from '@/types/account';

export interface BrokerUser {
	id: string;
	name: string;
	institution_id: Institution;
	accounts_synced: number;
	accounts_total: number;
}
