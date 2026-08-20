import type { Time } from 'lightweight-charts';

export type WaveDegree = 'cycle' | 'primary';

export type TargetWave = 'wave3' | 'wave5';

export interface WavePoint {
	wave: 1 | 2 | 3 | 4 | 5;
	time: Time;
	price: number;
}

export interface DegreeWaveCount {
	points: WavePoint[];
	wave3Target?: number | null;
	wave5Target?: number | null;
}

export interface SecurityElliottWaves {
	cycle?: DegreeWaveCount | null;
	primary?: DegreeWaveCount | null;
}

/**
 * Extracts the peak price of Wave 3 or Wave 5, respecting explicit wave3Target/wave5Target
 * overrides when set, or finding the corresponding wave point.
 */
export function getWaveTargetPrice(
	waveCount: DegreeWaveCount | null | undefined,
	targetWave: TargetWave
): number | null {
	if (!waveCount) {
		return null;
	}

	if (targetWave === 'wave3') {
		if (typeof waveCount.wave3Target === 'number' && !isNaN(waveCount.wave3Target)) {
			return waveCount.wave3Target;
		}
		if (Array.isArray(waveCount.points)) {
			const point = waveCount.points.find((p) => p && p.wave === 3);
			if (point && typeof point.price === 'number' && !isNaN(point.price)) {
				return point.price;
			}
		}
		return null;
	}

	if (targetWave === 'wave5') {
		if (typeof waveCount.wave5Target === 'number' && !isNaN(waveCount.wave5Target)) {
			return waveCount.wave5Target;
		}
		if (Array.isArray(waveCount.points)) {
			const point = waveCount.points.find((p) => p && p.wave === 5);
			if (point && typeof point.price === 'number' && !isNaN(point.price)) {
				return point.price;
			}
		}
		return null;
	}

	return null;
}

/**
 * Calculates upside/downside percentage from current price to target price:
 * ((targetPrice - currentPrice) / currentPrice) * 100
 * Safely returns null when inputs are non-numeric, nullish, or when currentPrice <= 0.
 */
export function calculateUpsidePercentage(
	targetPrice: number | null | undefined,
	currentPrice: number | null | undefined
): number | null {
	if (
		typeof targetPrice !== 'number' ||
		isNaN(targetPrice) ||
		!isFinite(targetPrice) ||
		typeof currentPrice !== 'number' ||
		isNaN(currentPrice) ||
		!isFinite(currentPrice) ||
		currentPrice <= 0
	) {
		return null;
	}

	return ((targetPrice - currentPrice) / currentPrice) * 100;
}

/**
 * Immutably updates the Elliott Wave configuration for a given security and degree.
 */
export function updateSecurityElliottWaves(
	existingWaves: Record<string, SecurityElliottWaves> | null | undefined,
	securityId: string,
	degree: WaveDegree,
	waveCount: DegreeWaveCount | null
): Record<string, SecurityElliottWaves> {
	const currentWaves = existingWaves ? { ...existingWaves } : {};
	const currentSecurity = currentWaves[securityId] ? { ...currentWaves[securityId] } : {};

	currentSecurity[degree] = waveCount;
	currentWaves[securityId] = currentSecurity;

	return currentWaves;
}

/**
 * Extracts the wave count for a specific security and degree from existing wave preferences.
 */
export function getSecurityDegreeWaveCount(
	existingWaves: Record<string, SecurityElliottWaves> | null | undefined,
	securityId: string,
	degree: WaveDegree
): DegreeWaveCount | null {
	if (!existingWaves || !securityId || !degree) {
		return null;
	}

	const securityWaves = existingWaves[securityId];
	if (!securityWaves) {
		return null;
	}

	return securityWaves[degree] ?? null;
}
