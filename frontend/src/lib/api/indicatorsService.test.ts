import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IndicatorsService } from './indicatorsService';

describe('IndicatorsService', () => {
	let service: IndicatorsService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		service = new IndicatorsService();
	});

	it('getPreferences fetches from /market/securities/:id/indicator-preferences', async () => {
		const mockPrefs = {
			security_id: 'sec-1',
			user_id: 'user-1',
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			}
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPrefs
		} as Response);

		const res = await service.getPreferences('sec-1');
		expect(res).toEqual(mockPrefs);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/indicator-preferences'),
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('savePreferences sends PUT request to /market/securities/:id/indicator-preferences', async () => {
		const mockPrefs = {
			security_id: 'sec-1',
			user_id: 'user-1',
			indicators: {
				sma: { enabled: true, color: '#ff0000', settings: { period: 20 } }
			}
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPrefs
		} as Response);

		const res = await service.savePreferences('sec-1', mockPrefs);
		expect(res).toEqual(mockPrefs);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/indicator-preferences'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify(mockPrefs)
			})
		);
	});

	it('getIndicatorData fetches from /market/securities/:id/indicators?type=:type', async () => {
		const mockData = {
			type: 'sma',
			label: 'SMA 20',
			color: '#ff0000',
			data: [{ time: '2026-01-01', value: 100 }]
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockData
		} as Response);

		const res = await service.getIndicatorData('sec-1', 'sma');
		expect(res).toEqual(mockData);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/indicators?type=sma'),
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('getAllIndicatorData fetches from /market/securities/:id/indicators', async () => {
		const mockData = [
			{
				type: 'sma',
				label: 'SMA 20',
				color: '#ff0000',
				data: [{ time: '2026-01-01', value: 100 }]
			}
		];
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockData
		} as Response);

		const res = await service.getAllIndicatorData('sec-1');
		expect(res).toEqual(mockData);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/indicators'),
			expect.objectContaining({ method: 'GET' })
		);
	});
});
