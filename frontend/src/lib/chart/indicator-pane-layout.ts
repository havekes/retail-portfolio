/**
 * Pure pane-height distribution math for the security chart.
 *
 * The chart has no native panes: every "pane" (main price, volume, and each
 * oscillator) is a separate price scale whose visible band is expressed with
 * `scaleMargins` (`top`/`bottom` fractions of the chart height). Stacking N
 * panes therefore means distributing those fractions so the bands do not
 * overlap.
 *
 * `computePaneScaleMargins` returns the exact same margins the chart used
 * before resizing existed whenever no custom heights are supplied, so the
 * default layout is preserved byte-for-byte by construction.
 */

export interface ScaleMargins {
	top: number;
	bottom: number;
}

export type PaneId = string;
export type PaneHeights = Record<string, number>;

export const MAIN_PANE_ID = 'main';
export const VOLUME_PANE_ID = 'volume';
export const OSCILLATOR_PANE_IDS = ['rsi', 'macd', 'obv'] as const;

/** Vertical gap between adjacent panes, as a fraction of the chart height. */
export const PANE_GAP = 0.02;
/** Breathing room above the whole pane stack, as a fraction of the chart height. */
export const TOP_MARGIN = 0.05;
/** Breathing room below the whole pane stack, as a fraction of the chart height. */
export const BOTTOM_MARGIN = 0;

/** A single pane may never render shorter than this fraction of the chart. */
export const MIN_PANE_FRACTION = 0.08;
/** A single pane may never render taller than this fraction of the chart. */
export const MAX_PANE_FRACTION = 0.8;

/**
 * Fallback relative weights used when a pane has no custom height and no
 * derived default. Oscillator values mirror the legacy `updatePanes()`
 * pane heights (0.25 / 0.18 / 0.14 by active count); main/volume are nominal.
 */
export const DEFAULT_PANE_HEIGHTS: Readonly<Record<string, number>> = Object.freeze({
	main: 0.5,
	volume: 0.15,
	rsi: 0.25,
	macd: 0.18,
	obv: 0.14
});

function round4(value: number): number {
	return Math.round(value * 10000) / 10000;
}

function clamp(value: number, min: number, max: number): number {
	if (!Number.isFinite(value)) return min;
	return Math.min(max, Math.max(min, value));
}

/**
 * The exact margins the chart applied before pane resizing existed. Kept as a
 * faithful port of `updatePanes()`'s hard-coded numbers so customising panes
 * never changes the default look.
 */
export function computeDefaultPaneScaleMargins(paneIds: PaneId[]): Record<string, ScaleMargins> {
	const margins: Record<string, ScaleMargins> = {};
	const activeOscillators = OSCILLATOR_PANE_IDS.filter((type) => paneIds.includes(type));
	const count = activeOscillators.length;
	const hasVolume = paneIds.includes(VOLUME_PANE_ID);

	if (count === 0) {
		if (hasVolume) {
			margins[VOLUME_PANE_ID] = { top: 0.7, bottom: 0 };
			margins[MAIN_PANE_ID] = { top: 0.1, bottom: 0.35 };
		} else {
			margins[MAIN_PANE_ID] = { top: 0.1, bottom: 0.1 };
		}
		return margins;
	}

	const paneHeight = count === 1 ? 0.25 : count === 2 ? 0.18 : 0.14;
	const gap = 0.02;
	const totalOscillatorHeight = count * paneHeight + count * gap;
	const mainAreaHeight = Math.max(0.3, 1.0 - totalOscillatorHeight);

	if (hasVolume) {
		const volumeHeight = round4(mainAreaHeight * 0.25);
		const volumeTop = round4(mainAreaHeight - volumeHeight);
		const volumeBottom = round4(1.0 - mainAreaHeight);
		margins[VOLUME_PANE_ID] = { top: volumeTop, bottom: volumeBottom };
		margins[MAIN_PANE_ID] = {
			top: 0.05,
			bottom: round4(1.0 - mainAreaHeight + volumeHeight + 0.03)
		};
	} else {
		margins[MAIN_PANE_ID] = {
			top: 0.05,
			bottom: round4(1.0 - mainAreaHeight + 0.03)
		};
	}

	activeOscillators.forEach((type, idx) => {
		const paneTop = round4(mainAreaHeight + gap + idx * (paneHeight + gap));
		const paneBottom = Math.max(0, round4(1.0 - (paneTop + paneHeight)));
		margins[type] = { top: paneTop, bottom: paneBottom };
	});

	return margins;
}

/** Default visible band height per pane, derived from the legacy margins. */
export function computeDefaultPaneHeights(paneIds: PaneId[]): PaneHeights {
	const margins = computeDefaultPaneScaleMargins(paneIds);
	const heights: PaneHeights = {};
	for (const id of paneIds) {
		const m = margins[id];
		heights[id] = m ? clamp(1 - m.top - m.bottom, MIN_PANE_FRACTION, MAX_PANE_FRACTION) : 0;
	}
	return heights;
}

/**
 * Split a total available height across panes proportionally to `weights`,
 * honouring the min/max clamp bounds. Water-filling: panes whose proportional
 * share would fall outside the bounds are pinned to the bound and the rest of
 * the space is redistributed among the remaining panes.
 */
export function allocatePaneHeights(weights: number[], target: number): number[] {
	const n = weights.length;
	if (n === 0) return [];
	const min = MIN_PANE_FRACTION;
	const max = MAX_PANE_FRACTION;
	if (target <= n * min) return weights.map(() => round4(target / n));
	if (target >= n * max) return weights.map(() => max);

	const result: (number | null)[] = new Array(n).fill(null);
	let remaining = target;
	let free = weights.map((_, i) => i);

	while (free.length > 0) {
		const freeSum = free.reduce((sum, i) => sum + weights[i], 0);
		const shares = free.map((i) =>
			freeSum > 0 ? (remaining * weights[i]) / freeSum : remaining / free.length
		);
		const allWithinBounds = shares.every((share) => share > min && share < max);

		if (allWithinBounds) {
			free.forEach((i, index) => {
				result[i] = shares[index];
			});
			break;
		}

		// Pin every out-of-bounds pane simultaneously, then redistribute the
		// remaining space across the panes still free.
		const stillFree: number[] = [];
		free.forEach((i, index) => {
			if (shares[index] <= min) {
				result[i] = min;
				remaining -= min;
			} else if (shares[index] >= max) {
				result[i] = max;
				remaining -= max;
			} else {
				stillFree.push(i);
			}
		});
		free = stillFree;
	}

	return result.map((value) => round4(value ?? min));
}

/**
 * Resolve the effective (clamped) weight for every pane: custom height when
 * valid, otherwise the legacy default band height.
 */
function resolvePaneWeights(paneIds: PaneId[], customHeights?: PaneHeights | null): number[] {
	const defaults = computeDefaultPaneHeights(paneIds);
	return paneIds.map((id) => {
		const custom = customHeights?.[id];
		const fallback = defaults[id] ?? DEFAULT_PANE_HEIGHTS[id] ?? 0.2;
		const value = typeof custom === 'number' && Number.isFinite(custom) ? custom : fallback;
		return clamp(value, MIN_PANE_FRACTION, MAX_PANE_FRACTION);
	});
}

/**
 * Distribute the vertical space available after margins and gaps across the
 * ordered panes, returning each pane's visible band height.
 */
export function distributePaneHeights(
	paneIds: PaneId[],
	customHeights?: PaneHeights | null
): PaneHeights {
	const n = paneIds.length;
	const heights: PaneHeights = {};
	if (n === 0) return heights;

	const available = Math.max(0, 1 - TOP_MARGIN - BOTTOM_MARGIN - (n - 1) * PANE_GAP);
	const weights = resolvePaneWeights(paneIds, customHeights);
	const allocations = allocatePaneHeights(weights, available);

	paneIds.forEach((id, index) => {
		heights[id] = allocations[index];
	});
	return heights;
}

/**
 * Compute `scaleMargins` for the ordered panes.
 *
 * With no (or empty) custom heights this is the exact legacy layout. With
 * custom heights the panes are clamped to [MIN, MAX], re-normalised to fill
 * the available space, and laid out top-to-bottom with fixed gaps so the
 * result is always non-overlapping and within [0, 1].
 */
export function computePaneScaleMargins(
	paneIds: PaneId[],
	customHeights?: PaneHeights | null
): Record<string, ScaleMargins> {
	const hasApplicableCustom =
		!!customHeights &&
		paneIds.some((id) => Object.prototype.hasOwnProperty.call(customHeights, id));
	if (!hasApplicableCustom || paneIds.length === 0) {
		return computeDefaultPaneScaleMargins(paneIds);
	}

	const heights = distributePaneHeights(paneIds, customHeights);
	const margins: Record<string, ScaleMargins> = {};
	let cursor = TOP_MARGIN;

	paneIds.forEach((id, index) => {
		const height = heights[id] ?? 0;
		margins[id] = {
			top: round4(cursor),
			bottom: round4(Math.max(0, 1 - (cursor + height)))
		};
		cursor += height;
		if (index < paneIds.length - 1) cursor += PANE_GAP;
	});

	return margins;
}

/** Visible band heights derived from `computePaneScaleMargins`. */
export function computePaneBandHeights(
	paneIds: PaneId[],
	customHeights?: PaneHeights | null
): PaneHeights {
	const margins = computePaneScaleMargins(paneIds, customHeights);
	const heights: PaneHeights = {};
	for (const id of paneIds) {
		const m = margins[id];
		heights[id] = m ? round4(Math.max(0, 1 - m.top - m.bottom)) : 0;
	}
	return heights;
}
