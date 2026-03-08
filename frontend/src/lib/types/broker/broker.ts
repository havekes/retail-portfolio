import { Institution } from '@/types/account';

export interface BrokerUser {
	id: string;
	displayName: string;
	institution_id: Institution;
}

export interface BackendInstitution {
	id: string;
	name: string;
	logo: string | null;
	auth_type: string;
	created_at: string;
}
