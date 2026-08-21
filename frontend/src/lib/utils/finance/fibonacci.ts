import type { Time } from 'lightweight-charts';

export type FibToolType = 'retracement' | 'extension';

export interface FibPoint {
	time: Time;
	price: number;
}

export interface FibLevelConfig {
	ratio: number;
	color?: string;
	enabled?: boolean;
	custom?: boolean;
}

export interface FibRetracementDrawing {
	id?: string;
	p1: FibPoint;
	p2: FibPoint;
	levels?: FibLevelConfig[] | null;
	extendLines?: boolean;
	visible?: boolean;
}

export interface FibExtensionDrawing {
	id?: string;
	p1: FibPoint;
	p2: FibPoint;
	p3: FibPoint;
	levels?: FibLevelConfig[] | null;
	extendLines?: boolean;
	visible?: boolean;
}

export interface SecurityFibonacciTools {
	retracement?: FibRetracementDrawing | null;
	extension?: FibExtensionDrawing | null;
}

export interface FibonacciPreferences {
	defaultRetracementLevels?: FibLevelConfig[] | null;
	defaultExtensionLevels?: FibLevelConfig[] | null;
	extendLines?: boolean;
}

export interface FibComputedLevel {
	ratio: number;
	price: number;
	formattedPrice: string;
	label: string;
	color?: string;
	enabled?: boolean;
}

export const DEFAULT_FIB_RETRACEMENT_LEVELS: FibLevelConfig[] = [
	{ ratio: 0.0, color: '#787B86', enabled: true },
	{ ratio: 0.236, color: '#F23645', enabled: true },
	{ ratio: 0.382, color: '#FF9800', enabled: true },
	{ ratio: 0.5, color: '#4CAF50', enabled: true },
	{ ratio: 0.618, color: '#089981', enabled: true },
	{ ratio: 0.786, color: '#00BCD4', enabled: true },
	{ ratio: 1.0, color: '#787B86', enabled: true },
	{ ratio: 1.618, color: '#2962FF', enabled: true }
];

export const DEFAULT_FIB_EXTENSION_LEVELS: FibLevelConfig[] = [
	{ ratio: 0.0, color: '#787B86', enabled: true },
	{ ratio: 0.382, color: '#FF9800', enabled: true },
	{ ratio: 0.5, color: '#4CAF50', enabled: true },
	{ ratio: 0.618, color: '#089981', enabled: true },
	{ ratio: 1.0, color: '#787B86', enabled: true },
	{ ratio: 1.272, color: '#9C27B0', enabled: true },
	{ ratio: 1.618, color: '#2962FF', enabled: true },
	{ ratio: 2.0, color: '#E91E63', enabled: true },
	{ ratio: 2.618, color: '#673AB7', enabled: true },
	{ ratio: 3.618, color: '#3F51B5', enabled: true },
	{ ratio: 4.236, color: '#009688', enabled: true }
];

/**
 * Formats a Fibonacci ratio and calculated price string (e.g. "0.618 (42.50)").
 * Safely handles invalid or non-finite numbers.
 */
export function formatFibLevelLabel(
	ratio: number | null | undefined,
	price: number | null | undefined,
	decimalPlaces: number = 2
): string {
	if (typeof ratio !== 'number' || isNaN(ratio) || !isFinite(ratio)) {
		return '';
	}
	if (typeof price !== 'number' || isNaN(price) || !isFinite(price)) {
		return `${ratio}`;
	}
	return `${ratio} (${price.toFixed(decimalPlaces)})`;
}

/**
 * Calculates Fibonacci retracement price levels between two anchor points P1 and P2.
 * Formula: price = p2.price - ratio * (p2.price - p1.price)
 * If levels is not provided, uses DEFAULT_FIB_RETRACEMENT_LEVELS.
 * Returns an empty array if inputs are invalid or missing.
 */
export function calculateRetracementLevels(
	p1: FibPoint | null | undefined,
	p2: FibPoint | null | undefined,
	levels?: (FibLevelConfig | number)[] | null
): FibComputedLevel[] {
	if (
		!p1 ||
		!p2 ||
		typeof p1.price !== 'number' ||
		isNaN(p1.price) ||
		!isFinite(p1.price) ||
		typeof p2.price !== 'number' ||
		isNaN(p2.price) ||
		!isFinite(p2.price)
	) {
		return [];
	}

	const configs = levels ?? DEFAULT_FIB_RETRACEMENT_LEVELS;
	if (!Array.isArray(configs) || configs.length === 0) {
		return [];
	}

	const delta = p2.price - p1.price;
	const computed: FibComputedLevel[] = [];

	for (const item of configs) {
		if (item == null) continue;
		const ratio = typeof item === 'number' ? item : item.ratio;
		const color = typeof item === 'object' ? item.color : undefined;
		const enabled = typeof item === 'object' ? (item.enabled ?? true) : true;

		if (typeof ratio !== 'number' || isNaN(ratio) || !isFinite(ratio)) {
			continue;
		}

		const price = p2.price - ratio * delta;
		computed.push({
			ratio,
			price,
			formattedPrice: price.toFixed(2),
			label: formatFibLevelLabel(ratio, price),
			color,
			enabled
		});
	}

	return computed;
}

/**
 * Calculates 3-point Trend-Based Fibonacci Extension price levels.
 * Formula: price = p3.price + ratio * (p2.price - p1.price)
 * If levels is not provided, uses DEFAULT_FIB_EXTENSION_LEVELS.
 * Returns an empty array if inputs are invalid or missing.
 */
export function calculateExtensionLevels(
	p1: FibPoint | null | undefined,
	p2: FibPoint | null | undefined,
	p3: FibPoint | null | undefined,
	levels?: (FibLevelConfig | number)[] | null
): FibComputedLevel[] {
	if (
		!p1 ||
		!p2 ||
		!p3 ||
		typeof p1.price !== 'number' ||
		isNaN(p1.price) ||
		!isFinite(p1.price) ||
		typeof p2.price !== 'number' ||
		isNaN(p2.price) ||
		!isFinite(p2.price) ||
		typeof p3.price !== 'number' ||
		isNaN(p3.price) ||
		!isFinite(p3.price)
	) {
		return [];
	}

	const configs = levels ?? DEFAULT_FIB_EXTENSION_LEVELS;
	if (!Array.isArray(configs) || configs.length === 0) {
		return [];
	}

	const move = p2.price - p1.price;
	const computed: FibComputedLevel[] = [];

	for (const item of configs) {
		if (item == null) continue;
		const ratio = typeof item === 'number' ? item : item.ratio;
		const color = typeof item === 'object' ? item.color : undefined;
		const enabled = typeof item === 'object' ? (item.enabled ?? true) : true;

		if (typeof ratio !== 'number' || isNaN(ratio) || !isFinite(ratio)) {
			continue;
		}

		const price = p3.price + ratio * move;
		computed.push({
			ratio,
			price,
			formattedPrice: price.toFixed(2),
			label: formatFibLevelLabel(ratio, price),
			color,
			enabled
		});
	}

	return computed;
}

/**
 * Immutably updates the Fibonacci tools for a given security.
 * Supports updating a specific tool ('retracement' or 'extension'), updating full/partial tool config,
 * or clearing tools when null is passed.
 */
export function updateSecurityFibonacciTools(
	existingTools: Record<string, SecurityFibonacciTools> | null | undefined,
	securityId: string,
	toolTypeOrTools: FibToolType | Partial<SecurityFibonacciTools> | null,
	drawing?: FibRetracementDrawing | FibExtensionDrawing | null
): Record<string, SecurityFibonacciTools> {
	if (!securityId) {
		return existingTools ? { ...existingTools } : {};
	}
	const result = existingTools ? { ...existingTools } : {};
	const currentSecurity = result[securityId] ? { ...result[securityId] } : {};

	if (typeof toolTypeOrTools === 'string') {
		if (toolTypeOrTools === 'retracement') {
			currentSecurity.retracement = (drawing as FibRetracementDrawing) ?? null;
		} else if (toolTypeOrTools === 'extension') {
			currentSecurity.extension = (drawing as FibExtensionDrawing) ?? null;
		}
	} else if (toolTypeOrTools === null) {
		result[securityId] = { retracement: null, extension: null };
		return result;
	} else if (typeof toolTypeOrTools === 'object') {
		if ('retracement' in toolTypeOrTools) {
			currentSecurity.retracement = toolTypeOrTools.retracement ?? null;
		}
		if ('extension' in toolTypeOrTools) {
			currentSecurity.extension = toolTypeOrTools.extension ?? null;
		}
	}

	result[securityId] = currentSecurity;
	return result;
}

/**
 * Safely extracts the Fibonacci tools for a specific security from the preferences dictionary.
 */
export function getSecurityFibonacciTools(
	existingTools: Record<string, SecurityFibonacciTools> | null | undefined,
	securityId: string
): SecurityFibonacciTools | null {
	if (!existingTools || !securityId) {
		return null;
	}
	return existingTools[securityId] ?? null;
}

/**
 * Compares two FibPoint objects for structural equality.
 */
export function areFibPointsEqual(
	a: FibPoint | null | undefined,
	b: FibPoint | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	return a.price === b.price && String(a.time) === String(b.time);
}

/**
 * Compares two FibLevelConfig arrays for structural equality.
 */
export function areFibLevelConfigsEqual(
	a: FibLevelConfig[] | null | undefined,
	b: FibLevelConfig[] | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (a.length !== b.length) return false;
	for (let i = 0; i < a.length; i++) {
		const itemA = a[i];
		const itemB = b[i];
		if (!itemA && !itemB) continue;
		if (!itemA || !itemB) return false;
		if (
			itemA.ratio !== itemB.ratio ||
			itemA.color !== itemB.color ||
			(itemA.enabled ?? true) !== (itemB.enabled ?? true) ||
			Boolean(itemA.custom) !== Boolean(itemB.custom)
		) {
			return false;
		}
	}
	return true;
}

/**
 * Compares two FibRetracementDrawing objects for structural equality.
 */
export function areRetracementDrawingsEqual(
	a: FibRetracementDrawing | null | undefined,
	b: FibRetracementDrawing | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (a.id !== b.id || a.extendLines !== b.extendLines || a.visible !== b.visible) {
		return false;
	}
	if (!areFibPointsEqual(a.p1, b.p1) || !areFibPointsEqual(a.p2, b.p2)) {
		return false;
	}
	if (!areFibLevelConfigsEqual(a.levels, b.levels)) {
		return false;
	}
	return true;
}

/**
 * Compares two FibExtensionDrawing objects for structural equality.
 */
export function areExtensionDrawingsEqual(
	a: FibExtensionDrawing | null | undefined,
	b: FibExtensionDrawing | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (a.id !== b.id || a.extendLines !== b.extendLines || a.visible !== b.visible) {
		return false;
	}
	if (
		!areFibPointsEqual(a.p1, b.p1) ||
		!areFibPointsEqual(a.p2, b.p2) ||
		!areFibPointsEqual(a.p3, b.p3)
	) {
		return false;
	}
	if (!areFibLevelConfigsEqual(a.levels, b.levels)) {
		return false;
	}
	return true;
}

/**
 * Compares two SecurityFibonacciTools objects for structural equality.
 */
export function areFibonacciToolsEqual(
	a: SecurityFibonacciTools | null | undefined,
	b: SecurityFibonacciTools | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (!areRetracementDrawingsEqual(a.retracement, b.retracement)) {
		return false;
	}
	if (!areExtensionDrawingsEqual(a.extension, b.extension)) {
		return false;
	}
	return true;
}
