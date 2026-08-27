import { ApiClient } from './apiClient';
import type { RewindDataWindow, RewindDrawings, RewindSnapshot } from '$lib/utils/finance/rewind';

export interface ChartSnapshotCreateRequest {
	drawings: RewindDrawings;
	data_window: RewindDataWindow;
	captured_at?: string | null;
}

export class SnapshotsService extends ApiClient {
	async getSnapshots(securityId: string, token?: string | null): Promise<RewindSnapshot[]> {
		return await this.get<RewindSnapshot[]>(
			`/market/securities/${securityId}/snapshots`,
			{},
			token
		);
	}

	async createSnapshot(
		securityId: string,
		request: ChartSnapshotCreateRequest,
		token?: string | null
	): Promise<RewindSnapshot> {
		return await this.post<RewindSnapshot, ChartSnapshotCreateRequest>(
			`/market/securities/${securityId}/snapshots`,
			request,
			{},
			token
		);
	}

	async deleteSnapshot(
		securityId: string,
		snapshotId: string,
		token?: string | null
	): Promise<void> {
		return await this.delete<void>(
			`/market/securities/${securityId}/snapshots/${snapshotId}`,
			{},
			token
		);
	}
}

export const getSnapshotsService = (customFetch?: typeof fetch) =>
	new SnapshotsService(customFetch);
export const snapshotsService = getSnapshotsService();
