import {
	getWaveTargetPrice,
	getWaveAlertPercent,
	type WaveDegree,
	type TargetWave,
	type WaveSettings,
	type SecurityElliottWaves
} from './elliott-wave';
import type { PriceAlert } from '$lib/api/alertsService';

/**
 * A desired wave-target price alert level. Matches `market_price_alerts.target_price`
 * semantics (percent of the wave target price) plus the derived condition.
 */
export interface WaveAlertLevel {
	degree: WaveDegree;
	wave: TargetWave;
	level: number;
	condition: 'above' | 'below';
}

const DEGREES: WaveDegree[] = ['cycle', 'primary'];
const TARGET_WAVES: TargetWave[] = ['wave3', 'wave5'];

/**
 * Rounds to 8 decimal places — matching `market_price_alerts.target_price DECIMAL(16,8)`
 * so the create→read-back round-trip compares exactly and reconcile stays idempotent.
 */
export function roundTo8dp(value: number): number {
	return Math.round(value * 1e8) / 1e8;
}

/**
 * Computes the desired wave-target alert levels for a security's waves against a set of
 * per-degree, per-wave percent settings. Pure and I/O-free.
 *
 * - Iterates deterministically over degree × target wave.
 * - A degree whose percent is null produces no level for that degree (per-degree independence).
 * - A degree without a valid target produces no level.
 * - `level = roundTo8dp(targetPrice × percent / 100)`.
 * - `condition = 'above'` when level > currentPrice, `'below'` when level < currentPrice;
 *   a level equal to currentPrice is skipped.
 */
export function computeWaveAlertLevels(
	settings: WaveSettings | null | undefined,
	securityWaves: SecurityElliottWaves | null | undefined,
	currentPrice: number | null | undefined
): WaveAlertLevel[] {
	if (typeof currentPrice !== 'number' || !isFinite(currentPrice) || currentPrice <= 0) {
		return [];
	}

	const levels: WaveAlertLevel[] = [];

	for (const degree of DEGREES) {
		for (const wave of TARGET_WAVES) {
			const percent = getWaveAlertPercent(settings, degree, wave);
			if (percent === null) continue;

			const targetPrice = getWaveTargetPrice(securityWaves?.[degree], wave);
			if (targetPrice === null) continue;

			const level = roundTo8dp((targetPrice * percent) / 100);

			if (level === currentPrice) continue;

			levels.push({
				degree,
				wave,
				level,
				condition: level > currentPrice ? 'above' : 'below'
			});
		}
	}

	return levels;
}

/**
 * A wave alert's reconcile identity — the columns actually comparable against the API
 * (degree/wave ride on the create payload, not on stored alerts).
 */
interface AlertIdentity {
	condition: 'above' | 'below';
	level: number;
}

function identityOf(condition: 'above' | 'below', level: number): AlertIdentity {
	return { condition, level: roundTo8dp(level) };
}

function identityKey(identity: AlertIdentity): string {
	return `${identity.condition}:${identity.level}`;
}

/**
 * Diffs existing price alerts against the desired levels and returns exactly which wave-source
 * alerts to delete and which levels to create. Manual alerts (`source !== 'wave'`) are never
 * returned in `toDelete`. Idempotent: a second run against fully-applied state yields empty sets.
 */
export function reconcileWaveAlerts(
	existingAlerts: PriceAlert[],
	desiredLevels: WaveAlertLevel[]
): { toCreate: WaveAlertLevel[]; toDelete: PriceAlert[] } {
	// Desired identities, deduped by (condition, level) — two degrees yielding the same
	// level+condition collapse to a single alert.
	const desiredKeys = new Set<string>();
	for (const level of desiredLevels) {
		desiredKeys.add(identityKey(identityOf(level.condition, level.level)));
	}

	const keptWaveKeys = new Set<string>();
	const toDelete: PriceAlert[] = [];
	for (const alert of existingAlerts) {
		if (alert.source !== 'wave') continue;
		// Normalize server Decimal (may serialize as string) to number at 8dp before keying.
		const key = identityKey(identityOf(alert.condition, Number(alert.target_price)));
		if (desiredKeys.has(key)) {
			keptWaveKeys.add(key);
		} else {
			toDelete.push(alert);
		}
	}

	const toCreate: WaveAlertLevel[] = [];
	for (const level of desiredLevels) {
		const key = identityKey(identityOf(level.condition, level.level));
		if (keptWaveKeys.has(key)) continue;
		toCreate.push(level);
		keptWaveKeys.add(key);
	}

	return { toCreate, toDelete };
}
