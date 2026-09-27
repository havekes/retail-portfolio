import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ValuationClient } from './valuationClient';

describe('ValuationClient', () => {
	let customFetch: ReturnType<typeof vi.fn>;
	let client: ValuationClient;

	beforeEach(() => {
		customFetch = vi.fn();
		client = new ValuationClient(customFetch as unknown as typeof fetch);
	});

	it('getValuation returns valuation object on success', async () => {
		const mockData = {
			id: 1,
			user_id: 'user-1',
			security_id: 'sec-1',
			lower_bound: 50.0,
			upper_bound: 100.0,
			created_at: '2026-01-01',
			updated_at: '2026-01-01'
		};
		customFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => mockData
		});

		const result = await client.getValuation('sec-1');
		expect(result).toEqual(mockData);
	});

	it('getValuation returns null when 404 is encountered', async () => {
		customFetch.mockResolvedValueOnce({
			ok: false,
			status: 404,
			statusText: 'Not Found',
			json: async () => ({ detail: 'Not found' })
		});

		const result = await client.getValuation('sec-1');
		expect(result).toBeNull();
	});

	it('saveValuation sends PUT request with lower_bound and upper_bound', async () => {
		const mockSaved = {
			id: 1,
			user_id: 'user-1',
			security_id: 'sec-1',
			lower_bound: 40.0,
			upper_bound: 80.0,
			created_at: '2026-01-01',
			updated_at: '2026-01-01'
		};
		customFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => mockSaved
		});

		const result = await client.saveValuation('sec-1', 40.0, 80.0);
		expect(result).toEqual(mockSaved);
		expect(customFetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/valuation'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify({ lower_bound: 40.0, upper_bound: 80.0 })
			})
		);
	});

	it('getBatchValuations sends POST request with list of security IDs', async () => {
		const mockList = [
			{
				id: 1,
				user_id: 'user-1',
				security_id: 'sec-1',
				lower_bound: 10.0,
				upper_bound: 20.0,
				created_at: '2026-01-01',
				updated_at: '2026-01-01'
			}
		];
		customFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => mockList
		});

		const result = await client.getBatchValuations(['sec-1']);
		expect(result).toEqual(mockList);
	});
});
