import type { WaveDegree } from '$lib/utils/finance/elliott-wave';

// Roman numerals for Cycle degree wave badges (TradingView convention).
const CYCLE_ROMAN_NUMERALS: Record<number, string> = {
	1: 'I',
	2: 'II',
	3: 'III',
	4: 'IV',
	5: 'V'
};

export interface DegreeVisualConfig {
	degree: WaveDegree;
	name: string;
	color: string;
	badgeBgColor: string;
	badgeTextColor: string;
	badgeBorderColor: string;
	hoverRingColor: string;
	lineWidth: number;
	nodeRadius: number;
	formatLabel: (wave: number) => string;
}

export const CYCLE_STYLE: DegreeVisualConfig = {
	degree: 'cycle',
	name: 'Cycle',
	color: '#3b82f6',
	badgeBgColor: '#1d4ed8',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#93c5fd',
	hoverRingColor: 'rgba(59, 130, 246, 0.4)',
	lineWidth: 2,
	nodeRadius: 10,
	formatLabel: (wave: number) => CYCLE_ROMAN_NUMERALS[wave] ?? ''
};

export const PRIMARY_STYLE: DegreeVisualConfig = {
	degree: 'primary',
	name: 'Primary',
	color: '#10b981',
	badgeBgColor: '#047857',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#6ee7b7',
	hoverRingColor: 'rgba(16, 185, 129, 0.4)',
	lineWidth: 2,
	nodeRadius: 9,
	formatLabel: (wave: number) => `${wave}`
};

export const DEGREE_STYLES: Record<WaveDegree, DegreeVisualConfig> = {
	cycle: CYCLE_STYLE,
	primary: PRIMARY_STYLE
};

export const HIT_TEST_RADIUS = 14;
export const MAX_WAVE_POINTS = 6;
export const PREVIEW_LINE_DASH = [4, 4];
export const PREVIEW_ALPHA = 0.65;
