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
	id: string;
	degree: WaveDegree;
	type: WaveType;
	points: WavePoint[];
	wave3Target?: number | null;
	wave5Target?: number | null;
}

export interface SecurityElliottWaves {
	waves: DegreeWaveCount[];
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
 * Deterministic 32-bit FNV-1a hash. Synchronous and environment-independent, used to derive
 * stable fallback wave ids — never `crypto` (async/variant availability in SSR and old contexts).
 */
function stableHash(input: string): string {
	let hash = 0x811c9dc5;
	for (let i = 0; i < input.length; i++) {
		hash ^= input.charCodeAt(i);
		hash = Math.imul(hash, 0x01000193);
	}
	return (hash >>> 0).toString(16).padStart(8, '0');
}

/**
 * Resolves a wave's identity. A persisted `id` always wins; otherwise a deterministic id is
 * derived from the wave's index, degree, type, and point positions. Deriving rather than
 * generating a random UUID keeps identity stable across loads/serializations, so re-loading a
 * wave collection without persisted ids does not change identities or make comparisons
 * spuriously differ. The index disambiguates otherwise-identical waves in one collection.
 */
export function getWaveIdentity(wave: DegreeWaveCount, index = 0): string {
	if (wave.id) return wave.id;
	const points = (wave.points ?? []).map((p) => `${p.wave}:${String(p.time)}:${p.price}`).join('|');
	return `wave-${index}-${wave.degree}-${wave.type}-${stableHash(points)}`;
}

/**
 * Normalizes a wave collection for storage/comparison: clones points, null-normalizes the
 * target fields, and assigns a stable id to every wave that lacks one (see `getWaveIdentity`).
 * Pure — never mutates the input.
 */
export function normalizeWaveIds(
	waves: readonly DegreeWaveCount[] | null | undefined
): DegreeWaveCount[] {
	return (waves ?? []).map((w, index) => ({
		...w,
		id: getWaveIdentity(w, index),
		points: Array.isArray(w.points) ? w.points.map((p) => ({ ...p })) : [],
		wave3Target: w.wave3Target ?? null,
		wave5Target: w.wave5Target ?? null
	}));
}

/**
 * Compares two SecurityElliottWaves objects for structural equality across their wave
 * collections. Both sides are id-normalized first, so a wave that has no persisted id compares
 * equal to its deterministic-id counterpart — round-tripping through state does not change
 * identity and does not spuriously report inequality.
 */
export function areSecurityElliottWavesEqual(
	a: SecurityElliottWaves | null | undefined,
	b: SecurityElliottWaves | null | undefined
): boolean {
	if (!a && !b) return true;
	const wavesA = normalizeWaveIds(a?.waves);
	const wavesB = normalizeWaveIds(b?.waves);
	if (wavesA.length !== wavesB.length) return false;

	for (let i = 0; i < wavesA.length; i++) {
		if (!areWaveCountsEqual(wavesA[i], wavesB[i])) {
			return false;
		}
	}

	return true;
}

/**
 * Immutably updates the Elliott Wave configuration for a given security.
 */
export function updateSecurityElliottWaves(
	existingWaves: Record<string, SecurityElliottWaves> | null | undefined,
	securityId: string,
	waves: DegreeWaveCount[]
): Record<string, SecurityElliottWaves> {
	const currentWaves = existingWaves ? { ...existingWaves } : {};
	currentWaves[securityId] = {
		waves: (waves ?? []).map((w) => ({
			...w,
			points: Array.isArray(w.points) ? w.points.map((p) => ({ ...p })) : []
		}))
	};
	return currentWaves;
}

/**
 * Selects the wave to represent a degree: the wave of the preferred type when one exists,
 * otherwise any wave of that degree. Callers that read persisted data use the default
 * (`impulse`, `'first'`) for a stable, insertion-order-independent choice; interactive callers
 * pass `prefer: 'last'` so the most recently drawn wave of the active type is targeted.
 */
export function selectDegreeWave(
	waves: readonly DegreeWaveCount[] | null | undefined,
	degree: WaveDegree,
	options: { preferredType?: WaveType; prefer?: 'first' | 'last' } = {}
): DegreeWaveCount | null {
	if (!waves || !Array.isArray(waves) || !degree) {
		return null;
	}

	const { preferredType = 'impulse', prefer = 'first' } = options;

	const pick = (matches: (w: DegreeWaveCount) => boolean): DegreeWaveCount | null => {
		if (prefer === 'last') {
			for (let i = waves.length - 1; i >= 0; i--) {
				const wave = waves[i];
				if (wave && matches(wave)) return wave;
			}
			return null;
		}
		return waves.find(matches) ?? null;
	};

	return (
		pick((w) => w.degree === degree && w.type === preferredType) ??
		pick((w) => w.degree === degree) ??
		null
	);
}

/**
 * Extracts the wave count for a specific security and degree from existing wave preferences,
 * preferring the impulse wave of that degree (see `selectDegreeWave`).
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
	if (!securityWaves || !Array.isArray(securityWaves.waves)) {
		return null;
	}

	return selectDegreeWave(securityWaves.waves, degree);
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
	if (a.id !== b.id) {
		return false;
	}
	if (a.degree !== b.degree) {
		return false;
	}
	if (a.type !== b.type) {
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
