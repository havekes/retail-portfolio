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
	1: '1',
	2: '2',
	3: '3',
	4: '4',
	5: '5'
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
	A: 'A',
	B: 'B',
	C: 'C'
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
	lineWidth: 1,
	nodeRadius: 6,
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
	lineWidth: 1,
	nodeRadius: 5,
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
	lineWidth: 1,
	nodeRadius: 5,
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

export const GRAND_SUPERCYCLE_STYLE: DegreeVisualConfig = {
	degree: 'grand_supercycle',
	name: 'Grand Supercycle',
	color: '#ec4899',
	badgeBgColor: '#be185d',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#f472b6',
	hoverRingColor: 'rgba(236, 72, 153, 0.4)',
	selectedRingColor: 'rgba(236, 72, 153, 0.7)',
	lineWidth: 1.5,
	nodeRadius: 7,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') return `[${wave}]`;
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? `[${letter}]` : '';
		}
		return typeof wave === 'number' ? `[${CYCLE_ROMAN_NUMERALS[wave] ?? wave}]` : '';
	}
};

export const SUPERCYCLE_STYLE: DegreeVisualConfig = {
	degree: 'supercycle',
	name: 'Supercycle',
	color: '#8b5cf6',
	badgeBgColor: '#6d28d9',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#c4b5fd',
	hoverRingColor: 'rgba(139, 92, 246, 0.4)',
	selectedRingColor: 'rgba(139, 92, 246, 0.7)',
	lineWidth: 1,
	nodeRadius: 6,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') return `(${wave})`;
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? `(${letter})` : '';
		}
		return typeof wave === 'number' ? `(${CYCLE_ROMAN_NUMERALS[wave] ?? wave})` : '';
	}
};

export const MINOR_STYLE: DegreeVisualConfig = {
	degree: 'minor',
	name: 'Minor',
	color: '#ef4444',
	badgeBgColor: '#b91c1c',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#fca5a5',
	hoverRingColor: 'rgba(239, 68, 68, 0.4)',
	selectedRingColor: 'rgba(239, 68, 68, 0.7)',
	lineWidth: 1,
	nodeRadius: 5,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') return wave;
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ?? '';
		}
		return typeof wave === 'number' ? String(wave) : '';
	}
};

export const MINUTE_STYLE: DegreeVisualConfig = {
	degree: 'minute',
	name: 'Minute',
	color: '#06b6d4',
	badgeBgColor: '#0e7490',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#67e8f9',
	hoverRingColor: 'rgba(6, 182, 212, 0.4)',
	selectedRingColor: 'rgba(6, 182, 212, 0.7)',
	lineWidth: 1,
	nodeRadius: 5,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		const lowerRoman: Record<number, string> = { 1: 'i', 2: 'ii', 3: 'iii', 4: 'iv', 5: 'v' };
		if (wave === 'A' || wave === 'B' || wave === 'C') return wave.toLowerCase();
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? letter.toLowerCase() : '';
		}
		return typeof wave === 'number' ? (lowerRoman[wave] ?? String(wave)) : '';
	}
};

export const MINUETTE_STYLE: DegreeVisualConfig = {
	degree: 'minuette',
	name: 'Minuette',
	color: '#84cc16',
	badgeBgColor: '#4d7c0f',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#bef264',
	hoverRingColor: 'rgba(132, 204, 22, 0.4)',
	selectedRingColor: 'rgba(132, 204, 22, 0.7)',
	lineWidth: 1,
	nodeRadius: 4,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		const lowerRoman: Record<number, string> = {
			1: '(i)',
			2: '(ii)',
			3: '(iii)',
			4: '(iv)',
			5: '(v)'
		};
		if (wave === 'A' || wave === 'B' || wave === 'C') return `(${wave.toLowerCase()})`;
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? `(${letter.toLowerCase()})` : '';
		}
		return typeof wave === 'number' ? (lowerRoman[wave] ?? `(${wave})`) : '';
	}
};

export const SUBMINUETTE_STYLE: DegreeVisualConfig = {
	degree: 'subminuette',
	name: 'Subminuette',
	color: '#f97316',
	badgeBgColor: '#c2410c',
	badgeTextColor: '#ffffff',
	badgeBorderColor: '#fdba74',
	hoverRingColor: 'rgba(249, 115, 22, 0.4)',
	selectedRingColor: 'rgba(249, 115, 22, 0.7)',
	lineWidth: 1,
	nodeRadius: 4,
	formatLabel: (wave: WavePointId, type?: WaveType) => {
		if (wave === 0) return '';
		if (wave === 'A' || wave === 'B' || wave === 'C') return wave.toLowerCase();
		if (type === 'corrective' && typeof wave === 'number') {
			const letter = NUMERIC_TO_CORRECTIVE_LETTER[wave];
			return letter ? letter.toLowerCase() : '';
		}
		return typeof wave === 'number' ? String(wave) : '';
	}
};

export const DEGREE_STYLES: Record<WaveDegree, DegreeVisualConfig> = {
	grand_supercycle: GRAND_SUPERCYCLE_STYLE,
	supercycle: SUPERCYCLE_STYLE,
	cycle: CYCLE_STYLE,
	primary: PRIMARY_STYLE,
	intermediate: INTERMEDIATE_STYLE,
	minor: MINOR_STYLE,
	minute: MINUTE_STYLE,
	minuette: MINUETTE_STYLE,
	subminuette: SUBMINUETTE_STYLE
};

export const HIT_TEST_RADIUS = 14;
/** Max pixel distance between the pointer and an active Fib level for wave points to snap to it. */
export const FIB_SNAP_TOLERANCE_PX = 8;
export const MAX_IMPULSE_POINTS = 6;
export const MAX_CORRECTIVE_POINTS = 4;
export const MAX_WAVE_POINTS = 6;
export const PREVIEW_LINE_DASH = [4, 4];
export const PREVIEW_ALPHA = 0.65;

export const HANDLE_RADIUS = 5;
export const DEFAULT_HANDLE_COLOR = '#2962FF';
export const DEFAULT_HANDLE_BORDER_COLOR = '#ffffff';
export const DEFAULT_DRAG_RING_COLOR = 'rgba(41, 98, 255, 0.35)';
export const DEFAULT_HOVER_RING_COLOR = 'rgba(41, 98, 255, 0.2)';
