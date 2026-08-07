import type { IndicatorConfig, IndicatorSettings } from './indicatorsService';

/** Numeric indicator config fields that the config modal outputs at the
 * top level and that must be promoted into the `settings` bag. */
interface IndicatorNumericFields {
	period?: number;
	stdDev?: number;
	fast?: number;
	slow?: number;
	signal?: number;
}

/** Shape the config modal and `onIndicatorConfigChange` emit —
 * IndicatorConfig plus the flat numeric fields. */
interface IndicatorConfigInput extends Partial<IndicatorConfig>, IndicatorNumericFields {}

/**
 * Build a preference entry `{ enabled, color, settings }` for a single
 * indicator.
 *
 * Numeric config fields (period, stdDev, fast, slow, signal) from the flat
 * `IndicatorConfigInput` are promoted into the `settings` bag so they survive
 * save/restore. Existing `settings` keys are preserved as a fallback.
 */
export function buildIndicatorEntry(
	newConfig: IndicatorConfigInput,
	current: IndicatorConfig | undefined
): IndicatorConfig {
	return {
		enabled: newConfig.enabled ?? current?.enabled ?? false,
		color: newConfig.color ?? current?.color ?? '',
		settings: buildSettings(newConfig, current)
	};
}

function buildSettings(
	newConfig: IndicatorConfigInput,
	current: IndicatorConfig | undefined
): IndicatorSettings {
	const result: IndicatorSettings = {
		...(newConfig.settings ?? {}),
		...(current?.settings ?? {}),
	};

	if (newConfig.period !== undefined) result.period = newConfig.period;
	if (newConfig.stdDev !== undefined) result.stdDev = newConfig.stdDev;
	if (newConfig.fast !== undefined) result.fast = newConfig.fast;
	if (newConfig.slow !== undefined) result.slow = newConfig.slow;
	if (newConfig.signal !== undefined) result.signal = newConfig.signal;

	return result;
}

/**
 * Build a preference entry for a toggle operation.
 * The enabled state is inverted from the current value; color falls back
 * to `indicatorConfigs` if not yet in the preference entry.
 */
export function buildToggleEntry(
	current: IndicatorConfig | undefined,
	indicatorColor: string,
	defaultEnabled: boolean | undefined
): IndicatorConfig {
	const currentEnabled = current?.enabled ?? defaultEnabled;
	const newEnabled = !currentEnabled;

	return {
		enabled: newEnabled,
		color: current?.color || indicatorColor || '',
		settings: current?.settings ?? {}
	};
}
