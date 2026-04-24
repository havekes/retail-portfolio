import type { Candle } from './candle';

export function calculateSMA(data: Candle[], period: number) {
	const smaData = [];
	for (let i = period - 1; i < data.length; i++) {
		let sum = 0;
		for (let j = 0; j < period; j++) {
			sum += data[i - j].close;
		}
		smaData.push({ time: data[i].time, value: sum / period });
	}
	return smaData;
}

export function calculateEMA(data: Candle[], period: number) {
	const emaData = new Array(data.length);
	const multiplier = 2 / (period + 1);

	let sum = 0;
	for (let i = 0; i < period; i++) {
		sum += data[i].close;
	}
	emaData[period - 1] = sum / period;

	for (let i = period; i < data.length; i++) {
		emaData[i] = (data[i].close - emaData[i - 1]) * multiplier + emaData[i - 1];
	}
	return emaData;
}
