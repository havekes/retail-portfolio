import type { Time } from 'lightweight-charts';

export type WaveDegree = 'cycle' | 'primary' | 'intermediate';

export type TargetWave = 'wave3' | 'wave5';

export interface WavePoint {
	wave: 0 | 1 | 2 | 3 | 4 | 5;
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
	intermediate?: DegreeWaveCount | null;
}

/**
 * Per-degree, per-wave alert percent settings (user-global). Each slot is `number | null`;
 * `null` disables that degree's wave-target alerts. Keys are snake_case for JSON parity.
 */
export interface WaveAlertPercents {
	cycle: { wave3: number | null; wave5: number | null };
	primary: { wave3: number | null; wave5: number | null };
	intermediate?: { wave3: number | null; wave5: number | null };
}

export interface WaveSettings {
	snap_to_wicks?: boolean | null;
	alert_percents?: WaveAlertPercents | null;
}

/**
 * App-wide default wave settings. Treat as read-only — do not mutate; consumers should
 * clone or spread this constant when building modified settings.
 */
export const DEFAULT_WAVE_SETTINGS: WaveSettings = {
	snap_to_wicks: null,
	alert_percents: {
		cycle: { wave3: null, wave5: null },
		primary: { wave3: null, wave5: null },
		intermediate: { wave3: null, wave5: null }
	}
};

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

/**
 * Returns the configured alert percent for a degree+wave, or null when the setting is
 * missing, disabled, or not a finite number.
 */
export function getWaveAlertPercent(
	settings: WaveSettings | null | undefined,
	degree: WaveDegree,
	targetWave: TargetWave
): number | null {
	if (!settings || !settings.alert_percents) {
		return null;
	}

	const degreePercents = settings.alert_percents[degree];
	if (!degreePercents) {
		return null;
	}

	const percent = degreePercents[targetWave];
	if (typeof percent !== 'number' || !isFinite(percent)) {
		return null;
	}

	return percent;
}

/**
 * Compares two DegreeWaveCount objects for structural equality.
 */
export function areWaveCountsEqual(
	a: DegreeWaveCount | null | undefined,
	b: DegreeWaveCount | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (a.wave3Target !== b.wave3Target || a.wave5Target !== b.wave5Target) {
		return false;
	}
	const aPoints = a.points || [];
	const bPoints = b.points || [];
	if (aPoints.length !== bPoints.length) {
		return false;
	}
	for (let i = 0; i < aPoints.length; i++) {
		const pA = aPoints[i];
		const pB = bPoints[i];
		if (!pA || !pB) return false;
		if (pA.wave !== pB.wave || pA.price !== pB.price || String(pA.time) !== String(pB.time)) {
			return false;
		}
	}
	return true;
}

/**
 * Compares two WaveSettings objects for structural equality. Optional fields are compared
 * nullish-normalized, so `undefined` and `null` (both meaning "off") compare equal.
 */
export function areWaveSettingsEqual(
	a: WaveSettings | null | undefined,
	b: WaveSettings | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;

	if ((a.snap_to_wicks ?? null) !== (b.snap_to_wicks ?? null)) {
		return false;
	}

	const aPercents = a.alert_percents ?? null;
	const bPercents = b.alert_percents ?? null;
	if (!aPercents && !bPercents) return true;
	if (!aPercents || !bPercents) return false;

	return (
		(aPercents.cycle?.wave3 ?? null) === (bPercents.cycle?.wave3 ?? null) &&
		(aPercents.cycle?.wave5 ?? null) === (bPercents.cycle?.wave5 ?? null) &&
		(aPercents.primary?.wave3 ?? null) === (bPercents.primary?.wave3 ?? null) &&
		(aPercents.primary?.wave5 ?? null) === (bPercents.primary?.wave5 ?? null) &&
		(aPercents.intermediate?.wave3 ?? null) === (bPercents.intermediate?.wave3 ?? null) &&
		(aPercents.intermediate?.wave5 ?? null) === (bPercents.intermediate?.wave5 ?? null)
	);
}
