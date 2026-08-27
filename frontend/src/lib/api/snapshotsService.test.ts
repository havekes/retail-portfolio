import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	SnapshotsService,
	getSnapshotsService,
	snapshotsService,
	type ChartSnapshotCreateRequest
} from './snapshotsService';
import { ApiError } from './apiClient';
import type { RewindSnapshot } from '$lib/utils/finance/rewind';

describe('SnapshotsService', () => {
	let service: SnapshotsService;

	const mockSnapshot: RewindSnapshot = {
		id: '00000000-0000-0000-0000-000000000001',
		security_id: 'sec-123',
		user_id: 'user-456',
		captured_at: '2026-08-27T10:00:00.000Z',
		created_at: '2026-08-27T10:00:01.000Z',
		drawings: {
			elliott_waves: null,
			fibonacci_tools: null
		},
		data_window: {
			first: '2026-01-01',
			last: '2026-06-01'
		}
	};

	const mockCreateRequest: ChartSnapshotCreateRequest = {
		drawings: {
			elliott_waves: null,
			fibonacci_tools: null
		},
		data_window: {
			first: '2026-01-01',
			last: '2026-06-01'
		},
		captured_at: '2026-08-27T10:00:00.000Z'
	};

	beforeEach(() => {
		vi.restoreAllMocks();
		global.fetch = vi.fn();
		service = new SnapshotsService();
	});

	describe('getSnapshots', () => {
		it('sends GET request to /market/securities/{securityId}/snapshots and returns snapshots', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => [mockSnapshot]
			} as Response);

			const result = await service.getSnapshots('sec-123');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots'),
				expect.objectContaining({
					method: 'GET',
					credentials: 'include',
					headers: expect.objectContaining({
						'Content-Type': 'application/json'
					})
				})
			);
			expect(result).toEqual([mockSnapshot]);
		});

		it('forwards authorization header when token is provided', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => [mockSnapshot]
			} as Response);

			await service.getSnapshots('sec-123', 'test-token');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots'),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: 'Bearer test-token'
					})
				})
			);
		});

		it('propagates ApiError on non-ok HTTP response', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 404,
				json: async () => ({ detail: 'Security not found' })
			} as Response);

			await expect(service.getSnapshots('sec-unknown')).rejects.toThrow(ApiError);
			await expect(service.getSnapshots('sec-unknown')).rejects.toThrow('Security not found');
		});
	});

	describe('createSnapshot', () => {
		it('sends POST request to /market/securities/{securityId}/snapshots with payload and returns created snapshot', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 201,
				json: async () => mockSnapshot
			} as Response);

			const result = await service.createSnapshot('sec-123', mockCreateRequest);

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots'),
				expect.objectContaining({
					method: 'POST',
					credentials: 'include',
					headers: expect.objectContaining({
						'Content-Type': 'application/json'
					}),
					body: JSON.stringify(mockCreateRequest)
				})
			);
			expect(result).toEqual(mockSnapshot);
		});

		it('forwards authorization header when token is provided', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 201,
				json: async () => mockSnapshot
			} as Response);

			await service.createSnapshot('sec-123', mockCreateRequest, 'test-token');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots'),
				expect.objectContaining({
					method: 'POST',
					headers: expect.objectContaining({
						Authorization: 'Bearer test-token'
					})
				})
			);
		});

		it('propagates ApiError on non-ok HTTP response', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 400,
				json: async () => ({ detail: 'Invalid snapshot data' })
			} as Response);

			await expect(service.createSnapshot('sec-123', mockCreateRequest)).rejects.toThrow(ApiError);
			await expect(service.createSnapshot('sec-123', mockCreateRequest)).rejects.toThrow(
				'Invalid snapshot data'
			);
		});
	});

	describe('deleteSnapshot', () => {
		it('sends DELETE request to /market/securities/{securityId}/snapshots/{snapshotId} and resolves cleanly on 204', async () => {
			const jsonMock = vi.fn();
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 204,
				json: jsonMock
			} as unknown as Response);

			const result = await service.deleteSnapshot('sec-123', 'snap-456');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots/snap-456'),
				expect.objectContaining({
					method: 'DELETE',
					credentials: 'include'
				})
			);
			expect(result).toBeUndefined();
			expect(jsonMock).not.toHaveBeenCalled();
		});

		it('forwards authorization header when token is provided', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 204,
				json: async () => undefined
			} as Response);

			await service.deleteSnapshot('sec-123', 'snap-456', 'test-token');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots/snap-456'),
				expect.objectContaining({
					method: 'DELETE',
					headers: expect.objectContaining({
						Authorization: 'Bearer test-token'
					})
				})
			);
		});

		it('propagates ApiError on non-ok HTTP response', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 404,
				json: async () => ({ detail: 'Snapshot not found' })
			} as Response);

			await expect(service.deleteSnapshot('sec-123', 'snap-unknown')).rejects.toThrow(ApiError);
			await expect(service.deleteSnapshot('sec-123', 'snap-unknown')).rejects.toThrow(
				'Snapshot not found'
			);
		});
	});

	describe('Factory and Singleton', () => {
		it('passes custom fetch to ApiClient when instantiated via getSnapshotsService', async () => {
			const customFetch = vi.fn().mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => [mockSnapshot]
			} as Response);

			const customService = getSnapshotsService(customFetch);
			const result = await customService.getSnapshots('sec-123');

			expect(customFetch).toHaveBeenCalledWith(
				expect.stringContaining('/api/v1/market/securities/sec-123/snapshots'),
				expect.objectContaining({ method: 'GET' })
			);
			expect(result).toEqual([mockSnapshot]);
			expect(global.fetch).not.toHaveBeenCalled();
		});

		it('exports singleton snapshotsService instance', () => {
			expect(snapshotsService).toBeInstanceOf(SnapshotsService);
		});
	});
});
