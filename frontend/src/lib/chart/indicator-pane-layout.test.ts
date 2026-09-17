import { describe, it, expect } from 'vitest';
import {
	allocatePaneHeights,
	computeDefaultPaneHeights,
	computeDefaultPaneScaleMargins,
	computePaneBandHeights,
	computePaneScaleMargins,
	distributePaneHeights,
	BOTTOM_MARGIN,
	MAX_PANE_FRACTION,
	MIN_PANE_FRACTION,
	PANE_GAP,
	TOP_MARGIN
} from './indicator-pane-layout';

function assertNonOverlapping(
	paneIds: string[],
	margins: Record<string, { top: number; bottom: number }>
) {
	for (const id of paneIds) {
		const m = margins[id];
		expect(m, `missing margins for ${id}`).toBeDefined();
		expect(m.top).toBeGreaterThanOrEqual(0);
		expect(m.bottom).toBeGreaterThanOrEqual(0);
		expect(m.top + m.bottom).toBeLessThanOrEqual(1);
	}
	// Adjacent panes never overlap: pane[i] ends before pane[i+1] starts.
	for (let i = 0; i < paneIds.length - 1; i++) {
		const upperEnd = 1 - margins[paneIds[i]].bottom;
		const lowerStart = margins[paneIds[i + 1]].top;
		expect(lowerStart).toBeGreaterThanOrEqual(upperEnd);
	}
}

describe('indicator-pane-layout defaults (AC3)', () => {
	it('reproduces the plain main-pane margins when no oscillators or volume exist', () => {
		expect(computeDefaultPaneScaleMargins(['main'])).toEqual({
			main: { top: 0.1, bottom: 0.1 }
		});
	});

	it('reproduces the volume-only fallback margins', () => {
		expect(computeDefaultPaneScaleMargins(['main', 'volume'])).toEqual({
			main: { top: 0.1, bottom: 0.35 },
			volume: { top: 0.7, bottom: 0 }
		});
	});

	it('reproduces legacy margins for one oscillator (count === 1)', () => {
		expect(computeDefaultPaneScaleMargins(['main', 'rsi'])).toEqual({
			main: { top: 0.05, bottom: 0.3 },
			rsi: { top: 0.75, bottom: 0 }
		});
	});

	it('reproduces legacy margins for two oscillators (count === 2)', () => {
		expect(computeDefaultPaneScaleMargins(['main', 'rsi', 'macd'])).toEqual({
			main: { top: 0.05, bottom: 0.43 },
			rsi: { top: 0.62, bottom: 0.2 },
			macd: { top: 0.82, bottom: 0 }
		});
	});

	it('reproduces legacy margins for three oscillators (count === 3)', () => {
		// paneHeight = 0.14, gap = 0.02, total = 0.48, mainAreaHeight = 0.52
		const margins = computeDefaultPaneScaleMargins(['main', 'rsi', 'macd', 'obv']);
		expect(margins.main).toEqual({ top: 0.05, bottom: 0.51 });
		expect(margins.rsi).toEqual({ top: 0.54, bottom: 0.32 });
		expect(margins.macd).toEqual({ top: 0.7, bottom: 0.16 });
		expect(margins.obv).toEqual({ top: 0.86, bottom: 0 });
	});

	it('reproduces legacy margins for volume + oscillator', () => {
		// paneHeight = 0.25, total = 0.27, mainAreaHeight = 0.73
		// volumeHeight = 0.1825, volumeTop = 0.5475, volumeBottom = 0.27
		expect(computeDefaultPaneScaleMargins(['main', 'volume', 'rsi'])).toEqual({
			main: { top: 0.05, bottom: 0.4825 },
			volume: { top: 0.5475, bottom: 0.27 },
			rsi: { top: 0.75, bottom: 0 }
		});
	});

	it('treats missing/empty custom heights as defaults', () => {
		const expected = computeDefaultPaneScaleMargins(['main', 'rsi']);
		expect(computePaneScaleMargins(['main', 'rsi'])).toEqual(expected);
		expect(computePaneScaleMargins(['main', 'rsi'], null)).toEqual(expected);
		expect(computePaneScaleMargins(['main', 'rsi'], {})).toEqual(expected);
	});

	it('falls back to defaults when custom keys match no present pane', () => {
		expect(computePaneScaleMargins(['main'], { rsi: 0.3, macd: 0.2 })).toEqual(
			computeDefaultPaneScaleMargins(['main'])
		);
	});
});

describe('indicator-pane-layout custom heights', () => {
	it('applies custom heights and fills the available space without overlap', () => {
		const paneIds = ['main', 'rsi'];
		const margins = computePaneScaleMargins(paneIds, { main: 0.5, rsi: 0.3 });
		assertNonOverlapping(paneIds, margins);

		const bands = computePaneBandHeights(paneIds, { main: 0.5, rsi: 0.3 });
		const available = 1 - TOP_MARGIN - BOTTOM_MARGIN - PANE_GAP;
		expect(bands.main + bands.rsi).toBeCloseTo(available, 3);
		// 0.5 : 0.3 ratio preserved by normalisation.
		expect(bands.main / bands.rsi).toBeCloseTo(0.5 / 0.3, 2);
	});

	it('clamps out-of-range custom heights to [MIN, MAX]', () => {
		const bands = computePaneBandHeights(['main', 'rsi'], { main: 99, rsi: -5 });
		expect(bands.main).toBeGreaterThan(0);
		expect(bands.rsi).toBeGreaterThan(0);
		expect(bands.main).toBeLessThanOrEqual(MAX_PANE_FRACTION);
		expect(bands.rsi).toBeGreaterThanOrEqual(MIN_PANE_FRACTION);

		const allocations = allocatePaneHeights([99, -5], 0.93);
		expect(allocations[0]).toBeLessThanOrEqual(MAX_PANE_FRACTION);
		expect(allocations[1]).toBeGreaterThanOrEqual(MIN_PANE_FRACTION);
	});

	it('keeps a valid layout when an oscillator is added or removed (AC4)', () => {
		const custom = { main: 0.45, rsi: 0.2, macd: 0.2 };
		const withAll = ['main', 'rsi', 'macd'];
		const afterRemove = ['main', 'macd'];

		const marginsAll = computePaneScaleMargins(withAll, custom);
		const marginsRemoved = computePaneScaleMargins(afterRemove, custom);

		assertNonOverlapping(withAll, marginsAll);
		assertNonOverlapping(afterRemove, marginsRemoved);
		// Only the panes present are returned.
		expect(Object.keys(marginsRemoved).sort()).toEqual(['macd', 'main']);
	});

	it('re-normalises so all panes plus gaps occupy the full height', () => {
		const paneIds = ['main', 'volume', 'rsi', 'macd'];
		const bands = computePaneBandHeights(paneIds, { main: 0.4, volume: 0.1, rsi: 0.3, macd: 0.05 });
		const totalBands = Object.values(bands).reduce((sum, value) => sum + value, 0);
		const gaps = (paneIds.length - 1) * PANE_GAP;
		expect(totalBands + gaps + TOP_MARGIN + BOTTOM_MARGIN).toBeCloseTo(1, 3);

		const margins = computePaneScaleMargins(paneIds, {
			main: 0.4,
			volume: 0.1,
			rsi: 0.3,
			macd: 0.05
		});
		assertNonOverlapping(paneIds, margins);
	});

	it('never lets two panes exceed the chart even with extreme custom values', () => {
		const paneIds = ['main', 'rsi', 'macd', 'obv'];
		const margins = computePaneScaleMargins(paneIds, {
			main: 100,
			rsi: 100,
			macd: 100,
			obv: 100
		});
		assertNonOverlapping(paneIds, margins);
		const last = margins['obv'];
		expect(1 - last.bottom).toBeLessThanOrEqual(1);
	});
});

describe('allocatePaneHeights', () => {
	it('splits proportionally when within bounds', () => {
		expect(allocatePaneHeights([1, 1], 0.5)).toEqual([0.25, 0.25]);
	});

	it('pins panes at the maximum when the requested target is large', () => {
		const result = allocatePaneHeights([1, 1], 5);
		expect(result).toEqual([MAX_PANE_FRACTION, MAX_PANE_FRACTION]);
	});

	it('distributes evenly when the target is below the combined minimum', () => {
		const result = allocatePaneHeights([1, 1], 0.1);
		expect(result[0]).toBeCloseTo(0.05, 4);
		expect(result[1]).toBeCloseTo(0.05, 4);
	});

	it('water-fills: one pane pinned at max, the rest share the remainder', () => {
		const result = allocatePaneHeights([10, 1, 1], 1.0);
		expect(result[0]).toBe(MAX_PANE_FRACTION);
		expect(result[1] + result[2]).toBeCloseTo(1.0 - MAX_PANE_FRACTION, 3);
	});

	it('water-fills: small panes pinned at min receive the minimum', () => {
		const result = allocatePaneHeights([10, 1, 1], 0.6);
		expect(result[0]).toBeCloseTo(0.44, 3);
		expect(result[1]).toBe(MIN_PANE_FRACTION);
		expect(result[2]).toBe(MIN_PANE_FRACTION);
	});
});

describe('computeDefaultPaneHeights', () => {
	it('derives band heights from the legacy margins', () => {
		const heights = computeDefaultPaneHeights(['main', 'volume']);
		expect(heights.main).toBeCloseTo(0.55, 4);
		expect(heights.volume).toBeCloseTo(0.3, 4);
	});
});

describe('distributePaneHeights', () => {
	it('returns an empty record for no panes', () => {
		expect(distributePaneHeights([], { main: 0.5 })).toEqual({});
	});

	it('ignores custom keys for panes that are not present', () => {
		const heights = distributePaneHeights(['main'], { main: 0.5, rsi: 0.9 });
		expect(Object.keys(heights)).toEqual(['main']);
	});
});
