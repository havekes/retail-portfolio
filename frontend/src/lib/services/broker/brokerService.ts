import { BaseService } from '../baseService';
import type { BrokerUser } from '@/types/broker/broker';

export class BrokerService extends BaseService {
	async getBrokerUsers(): Promise<BrokerUser[]> {
		return this.get<BrokerUser[]>('/broker-users');
	}
}

export const brokerService = new BrokerService();
