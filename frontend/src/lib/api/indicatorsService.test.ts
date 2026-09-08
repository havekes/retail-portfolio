import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	IndicatorsService,
	getIndicatorsService,
	type IndicatorComputeRequest
} from './indicatorsService';
import { ApiError } from './apiClient';

describe('IndicatorsService', () => {
	let service: IndicatorsService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		service = new IndicatorsService();
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

	it('computeIndicators sends POST request with serialized body and returns parsed response', async () => {
		const requestPayload: IndicatorComputeRequest = {
			interval: '1d',
			chart_style: 'candlestick',
			indicators: [{ id: 'ma50', type: 'ma50', period: 50 }],
			candles: [{ time: '2026-01-01', open: 10, high: 12, low: 9, close: 11, volume: 100 }]
		};
		const mockResponse = {
			indicators: {
				ma50: [{ time: '2026-01-01', value: 11 }]
			}
		};

		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const res = await service.computeIndicators('sec-123', requestPayload);
		expect(res).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-123/indicators/compute'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({
					'Content-Type': 'application/json'
				}),
				body: JSON.stringify(requestPayload)
			})
		);
	});

	it('computeIndicators propagates ApiError when request fails', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 500,
			json: async () => ({ detail: 'Internal indicator calculation error' })
		} as Response);

		const requestPayload: IndicatorComputeRequest = {
			interval: '1d',
			indicators: [{ type: 'rsi', period: 14 }]
		};

		await expect(service.computeIndicators('sec-123', requestPayload)).rejects.toThrow(ApiError);
		await expect(service.computeIndicators('sec-123', requestPayload)).rejects.toMatchObject({
			status: 500,
			message: 'Internal indicator calculation error'
		});
	});

	it('passes custom fetch when instantiated via getIndicatorsService', async () => {
		const customFetch = vi.fn().mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ indicators: {} })
		} as Response);

		const customService = getIndicatorsService(customFetch);
		await customService.computeIndicators('sec-1', { interval: '1d', indicators: [] });

		expect(customFetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/indicators/compute'),
			expect.objectContaining({ method: 'POST' })
		);
	});
});
