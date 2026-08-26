import type { WaveDegree, WavePointId, WaveType } from '$lib/utils/finance/elliott-wave';

// Roman numerals for Cycle degree wave badges (TradingView convention).
const CYCLE_ROMAN_NUMERALS: Record<number, string> = {
	1: 'I',
	2: 'II',
	3: 'III',
	4: 'IV',
	5: 'V'
};

const PRIMARY_CIRCLED_NUMBERS: Record<number, string> = {
	1: '①',
	2: '②',
	3: '③',
	4: '④',
	5: '⑤'
};

const INTERMEDIATE_PARENTHESES_NUMBERS: Record<number, string> = {
	1: '(1)',
	2: '(2)',
	3: '(3)',
	4: '(4)',
	5: '(5)'
};

// Corrective wave labels: Cycle (A, B, C), Primary (Ⓐ, Ⓑ, Ⓒ), Intermediate ((A), (B), (C))
const CYCLE_CORRECTIVE_LABELS: Record<string, string> = {
	A: 'A',
	B: 'B',
	C: 'C'
};

const PRIMARY_CORRECTIVE_LABELS: Record<string, string> = {
	A: 'Ⓐ',
	B: 'Ⓑ',
	C: 'Ⓒ'
};

const INTERMEDIATE_CORRECTIVE_LABELS: Record<string, string> = {
	A: '(A)',
	B: '(B)',
	C: '(C)'
};

const NUMERIC_TO_CORRECTIVE_LETTER: Record<number, 'A' | 'B' | 'C'> = {
	1: 'A',
	2: 'B',
	3: 'C'
};

export interface DegreeVisualConfig {
	degree: WaveDegree;
	name: string;
	color: string;
	badgeBgColor: string;
	badgeTextColor: string;
	badgeBorderColor: string;
	hoverRingColor: string;
	selectedRingColor?: string;
	lineWidth: number;
	nodeRadius: number;
	formatLabel: (wave: WavePointId, type?: WaveType) => string;
}

export const CYCLE_STYLE: DegreeVisualConfig = {
	degree: 'cycle',
	name: 'Cycle',
	color: '#3b82f6',
	badgeBgColor: '#1d4ed8',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#93c5fd',
	hoverRingColor: 'rgba(59, 130, 246, 0.4)',
	selectedRingColor: 'rgba(59, 130, 246, 0.7)',
	lineWidth: 2,
	nodeRadius: 10,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') {
			return CYCLE_CORRECTIVE_LABELS[wave] ?? '';
		}
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? (CYCLE_CORRECTIVE_LABELS[letter] ?? '') : '';
		}
		return typeof wave === 'number' ? (CYCLE_ROMAN_NUMERALS[wave] ?? '') : '';
	}
};

export const PRIMARY_STYLE: DegreeVisualConfig = {
	degree: 'primary',
	name: 'Primary',
	color: '#10b981',
	badgeBgColor: '#047857',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#6ee7b7',
	hoverRingColor: 'rgba(16, 185, 129, 0.4)',
	selectedRingColor: 'rgba(16, 185, 129, 0.7)',
	lineWidth: 2,
	nodeRadius: 9,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') {
			return PRIMARY_CORRECTIVE_LABELS[wave] ?? '';
		}
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? (PRIMARY_CORRECTIVE_LABELS[letter] ?? '') : '';
		}
		return typeof wave === 'number' ? (PRIMARY_CIRCLED_NUMBERS[wave] ?? '') : '';
	}
};

export const INTERMEDIATE_STYLE: DegreeVisualConfig = {
	degree: 'intermediate',
	name: 'Intermediate',
	color: '#f59e0b',
	badgeBgColor: '#b45309',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#fcd34d',
	hoverRingColor: 'rgba(245, 158, 11, 0.4)',
	selectedRingColor: 'rgba(245, 158, 11, 0.7)',
	lineWidth: 2,
	nodeRadius: 9,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') {
			return INTERMEDIATE_CORRECTIVE_LABELS[wave] ?? '';
		}
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? (INTERMEDIATE_CORRECTIVE_LABELS[letter] ?? '') : '';
		}
		return typeof wave === 'number' ? (INTERMEDIATE_PARENTHESES_NUMBERS[wave] ?? '') : '';
	}
};

export const DEGREE_STYLES: Record<WaveDegree, DegreeVisualConfig> = {
	cycle: CYCLE_STYLE,
	primary: PRIMARY_STYLE,
	intermediate: INTERMEDIATE_STYLE
};

export const HIT_TEST_RADIUS = 14;
export const MAX_IMPULSE_POINTS = 6;
export const MAX_CORRECTIVE_POINTS = 4;
export const MAX_WAVE_POINTS = 6;
export const PREVIEW_LINE_DASH = [4, 4];
export const PREVIEW_ALPHA = 0.65;
