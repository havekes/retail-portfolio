import type { Time } from 'lightweight-charts';

export type WaveDegree = 'cycle' | 'primary' | 'intermediate';

export type WaveType = 'impulse' | 'corrective';

export type WavePointId = 0 | 1 | 2 | 3 | 4 | 5 | 'A' | 'B' | 'C';

export type TargetWave = 'wave3' | 'wave5';

export interface WavePoint {
	wave: WavePointId;
	time: Time;
	price: number;
}

export interface DegreeWaveCount {
	id?: string;
	degree?: WaveDegree;
	type?: WaveType;
	points: WavePoint[];
	wave3Target?: number | null;
	wave5Target?: number | null;
}

export interface SecurityElliottWaves {
	cycle?: DegreeWaveCount | null;
	primary?: DegreeWaveCount | null;
	intermediate?: DegreeWaveCount | null;
	waves?: DegreeWaveCount[] | null;
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
 * Normalizes a SecurityElliottWaves object by populating both legacy degree slots
 * and the multi-wave `waves` array.
 */
export function normalizeSecurityElliottWaves(
	waves: SecurityElliottWaves | null | undefined
): SecurityElliottWaves {
	if (!waves) {
		return { cycle: null, primary: null, intermediate: null, waves: [] };
	}

	const waveList: DegreeWaveCount[] = [];
	if (Array.isArray(waves.waves)) {
		for (const w of waves.waves) {
			if (w) {
				waveList.push({
					...w,
					degree: w.degree ?? 'cycle',
					type:
						w.type ??
						(w.points?.some((p) => p.wave === 'A' || p.wave === 'B' || p.wave === 'C')
							? 'corrective'
							: 'impulse'),
					points: Array.isArray(w.points) ? w.points.map((p) => ({ ...p })) : []
				});
			}
		}
	} else {
		const degrees: WaveDegree[] = ['cycle', 'primary', 'intermediate'];
		for (const deg of degrees) {
			const slot = waves[deg];
			if (slot && Array.isArray(slot.points) && slot.points.length > 0) {
				waveList.push({
					...slot,
					degree: slot.degree ?? deg,
					type:
						slot.type ??
						(slot.points.some((p) => p.wave === 'A' || p.wave === 'B' || p.wave === 'C')
							? 'corrective'
							: 'impulse'),
					points: slot.points.map((p) => ({ ...p }))
				});
			}
		}
	}

	const cycle = waves.cycle ?? waveList.find((w) => w.degree === 'cycle') ?? null;
	const primary = waves.primary ?? waveList.find((w) => w.degree === 'primary') ?? null;
	const intermediate =
		waves.intermediate ?? waveList.find((w) => w.degree === 'intermediate') ?? null;

	return {
		cycle: cycle ? { ...cycle, points: [...cycle.points] } : null,
		primary: primary ? { ...primary, points: [...primary.points] } : null,
		intermediate: intermediate ? { ...intermediate, points: [...intermediate.points] } : null,
		waves: waveList
	};
}

/**
 * Returns all wave counts for a security, either from the `waves` collection or from legacy slots.
 */
export function getSecurityWaveCounts(
	waves: SecurityElliottWaves | null | undefined
): DegreeWaveCount[] {
	if (!waves) return [];
	if (Array.isArray(waves.waves)) {
		return waves.waves;
	}
	const result: DegreeWaveCount[] = [];
	const degrees: WaveDegree[] = ['cycle', 'primary', 'intermediate'];
	for (const deg of degrees) {
		const count = waves[deg];
		if (count && Array.isArray(count.points) && count.points.length > 0) {
			result.push({
				...count,
				degree: count.degree ?? deg
			});
		}
	}
	return result;
}

/**
 * Compares two SecurityElliottWaves objects for structural equality across both legacy slots and multi-wave collections.
 */
export function areSecurityElliottWavesEqual(
	a: SecurityElliottWaves | null | undefined,
	b: SecurityElliottWaves | null | undefined
): boolean {
	if (!a && !b) return true;
	const normA = normalizeSecurityElliottWaves(a);
	const normB = normalizeSecurityElliottWaves(b);

	const wavesA = normA.waves || [];
	const wavesB = normB.waves || [];
	if (wavesA.length !== wavesB.length) return false;

	for (let i = 0; i < wavesA.length; i++) {
		if (!areWaveCountsEqual(wavesA[i], wavesB[i])) {
			return false;
		}
	}

	if (!areWaveCountsEqual(normA.cycle, normB.cycle)) return false;
	if (!areWaveCountsEqual(normA.primary, normB.primary)) return false;
	if (!areWaveCountsEqual(normA.intermediate, normB.intermediate)) return false;

	return true;
}

/**
 * Immutably updates the Elliott Wave configuration for a given security and degree or full collection.
 */
export function updateSecurityElliottWaves(
	existingWaves: Record<string, SecurityElliottWaves> | null | undefined,
	securityId: string,
	degreeOrWaves: WaveDegree | SecurityElliottWaves | DegreeWaveCount[],
	maybeWaveCount?: DegreeWaveCount | null
): Record<string, SecurityElliottWaves> {
	const currentWaves = existingWaves ? { ...existingWaves } : {};
	const currentSecurity = currentWaves[securityId] ? { ...currentWaves[securityId] } : {};

	if (typeof degreeOrWaves === 'string') {
		const degree = degreeOrWaves as WaveDegree;
		const waveCount = maybeWaveCount ?? null;

		currentSecurity[degree] = waveCount;

		if (Array.isArray(currentSecurity.waves)) {
			let wavesList = [...currentSecurity.waves];
			if (waveCount === null) {
				wavesList = wavesList.filter((w) => w.degree !== degree);
			} else {
				const existingIdx = waveCount.id
					? wavesList.findIndex((w) => w.id === waveCount.id)
					: wavesList.findIndex(
							(w) => w.degree === degree && (w.type ?? 'impulse') === (waveCount.type ?? 'impulse')
						);
				const normalizedWave = { ...waveCount, degree };
				if (existingIdx !== -1) {
					wavesList[existingIdx] = normalizedWave;
				} else {
					wavesList.push(normalizedWave);
				}
			}
			currentSecurity.waves = wavesList;
		}

		currentWaves[securityId] = currentSecurity;
		return currentWaves;
	}

	if (Array.isArray(degreeOrWaves)) {
		const wavesList = [...degreeOrWaves];
		currentSecurity.waves = wavesList;
		currentSecurity.cycle = wavesList.find((w) => w.degree === 'cycle') ?? null;
		currentSecurity.primary = wavesList.find((w) => w.degree === 'primary') ?? null;
		currentSecurity.intermediate = wavesList.find((w) => w.degree === 'intermediate') ?? null;
		currentWaves[securityId] = currentSecurity;
		return currentWaves;
	}

	if (typeof degreeOrWaves === 'object' && degreeOrWaves !== null) {
		const normalized = normalizeSecurityElliottWaves(degreeOrWaves as SecurityElliottWaves);
		currentWaves[securityId] = normalized;
		return currentWaves;
	}

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

	if (securityWaves[degree]) {
		return securityWaves[degree]!;
	}

	if (Array.isArray(securityWaves.waves)) {
		return securityWaves.waves.find((w) => w.degree === degree) ?? null;
	}

	return null;
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
	if (a.id !== undefined && b.id !== undefined && a.id !== b.id) {
		return false;
	}
	if (a.degree !== undefined && b.degree !== undefined && a.degree !== b.degree) {
		return false;
	}
	if ((a.type ?? 'impulse') !== (b.type ?? 'impulse')) {
		return false;
	}
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
