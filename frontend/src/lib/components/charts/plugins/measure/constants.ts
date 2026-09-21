import type { MeasureDirection } from '$lib/utils/finance/measure';

export const HIT_TEST_RADIUS = 14;
export const PREVIEW_LINE_DASH = [4, 4];
export const PREVIEW_ALPHA = 0.65;

export const MEASURE_LINE_WIDTH = 1.5;
export const MEASURE_FILL_ALPHA = 0.12;

export const MEASURE_UP_COLOR = '#089981';
export const MEASURE_DOWN_COLOR = '#f23645';
export const MEASURE_FLAT_COLOR = '#787B86';

export const MEASURE_COLORS: Record<MeasureDirection, string> = {
	up: MEASURE_UP_COLOR,
	down: MEASURE_DOWN_COLOR,
	flat: MEASURE_FLAT_COLOR
};

/** Resolves the direction-aware colour used for the measure line and label. */
export function measureColor(direction: MeasureDirection): string {
	return MEASURE_COLORS[direction] ?? MEASURE_FLAT_COLOR;
}

export const MEASURE_LABEL_BG_COLOR = '#131722';
export const MEASURE_LABEL_TEXT_COLOR = '#ffffff';
export const MEASURE_LABEL_HEIGHT = 18;
export const MEASURE_LABEL_FONT_SIZE = 11;
export const MEASURE_LABEL_PADDING_X = 6;
/** Rough per-character width for the 11px sans-serif label font. */
export const MEASURE_LABEL_CHAR_WIDTH = 6.2;
