export interface Candle {
	time: string;
	open: number;
	high: number;
	low: number;
	close: number;
	volume?: number;
}

export function convertToHeikinAshi(candles: Candle[]): Candle[] {
	const result: Candle[] = [];

	for (let i = 0; i < candles.length; i++) {
		const candle = candles[i];

		if (i === 0) {
			// First candle: calculate initial HA values
			const haClose = (candle.open + candle.high + candle.low + candle.close) / 4;
			const haOpen = (candle.open + candle.close) / 2;
			result.push({
				time: candle.time,
				open: haOpen,
				close: haClose,
				high: Math.max(candle.high, haOpen, haClose),
				low: Math.min(candle.low, haOpen, haClose),
				volume: candle.volume
			});
			continue;
		}

		// Get previous HA candle
		const prevHA = result[i - 1];

		// Heikin Ashi formulas
		const haClose = (candle.open + candle.high + candle.low + candle.close) / 4;
		const haOpen = (prevHA.open + prevHA.close) / 2;
		const haHigh = Math.max(candle.high, haOpen, haClose);
		const haLow = Math.min(candle.low, haOpen, haClose);

		result.push({
			time: candle.time,
			open: haOpen,
			high: haHigh,
			low: haLow,
			close: haClose,
			volume: candle.volume
		});
	}

	return result;
}
