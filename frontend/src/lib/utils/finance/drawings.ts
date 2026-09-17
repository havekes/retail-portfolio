import type { Time } from 'lightweight-charts';

/**
 * Tool identifiers for the new drawing tools. Each maps to a per-security
 * collection in {@link SecurityDrawings}.
 */
export type DrawingToolType = 'measures' | 'horizontalLines' | 'lines';

/**
 * A single anchor point of a drawing. Deliberately independent from the
 * Fibonacci/Elliott point types so this module stays plugin-agnostic
 * (no cross-plugin coupling).
 */
export interface DrawingPoint {
	time: Time;
	price: number;
}

/** Two-point measurement drawing. */
export interface MeasureDrawing {
	id?: string;
	p1: DrawingPoint;
	p2: DrawingPoint;
	visible?: boolean;
}

/** One-point horizontal line drawing. */
export interface HorizontalLineDrawing {
	id?: string;
	p1: DrawingPoint;
	visible?: boolean;
}

/** Two-point free-form line drawing. */
export interface LineDrawing {
	id?: string;
	p1: DrawingPoint;
	p2: DrawingPoint;
	visible?: boolean;
}

export type Drawing = MeasureDrawing | HorizontalLineDrawing | LineDrawing;

/**
 * Per-security collections of the new drawing tools. Each collection is
 * optional; missing/null/empty all mean "no drawings for that tool".
 */
export interface SecurityDrawings {
	measures?: MeasureDrawing[] | null;
	horizontalLines?: HorizontalLineDrawing[] | null;
	lines?: LineDrawing[] | null;
}

/** Preferences dictionary keyed by security id. */
export type SecurityDrawingsMap = Record<string, SecurityDrawings>;

/**
 * Safely extracts the new-tool drawings for a specific security from the
 * preferences dictionary.
 */
export function getSecurityDrawings(
	existing: SecurityDrawingsMap | null | undefined,
	securityId: string
): SecurityDrawings | null {
	if (!existing || !securityId) {
		return null;
	}
	return existing[securityId] ?? null;
}

/**
 * Immutably replaces the drawing collection for a given security + tool type.
 * Passing `null` clears the collection. Other tool types on the same security
 * and all other securities are preserved.
 */
export function updateSecurityDrawings(
	existing: SecurityDrawingsMap | null | undefined,
	securityId: string,
	toolType: DrawingToolType,
	drawings: Drawing[] | null | undefined
): SecurityDrawingsMap {
	if (!securityId) {
		return existing ? { ...existing } : {};
	}
	const result = existing ? { ...existing } : {};
	const current: SecurityDrawings = result[securityId] ? { ...result[securityId] } : {};

	if (toolType === 'measures') {
		current.measures = (drawings as MeasureDrawing[] | null | undefined) ?? null;
	} else if (toolType === 'horizontalLines') {
		current.horizontalLines = (drawings as HorizontalLineDrawing[] | null | undefined) ?? null;
	} else if (toolType === 'lines') {
		current.lines = (drawings as LineDrawing[] | null | undefined) ?? null;
	}

	result[securityId] = current;
	return result;
}

/**
 * Immutably appends a drawing to (or replaces a same-id drawing in) the
 * collection for a given security + tool type. Other tool types and other
 * securities are preserved; the input map and arrays are never mutated.
 */
export function addOrReplaceDrawing(
	existing: SecurityDrawingsMap | null | undefined,
	securityId: string,
	toolType: DrawingToolType,
	drawing: Drawing
): SecurityDrawingsMap {
	if (!securityId) {
		return existing ? { ...existing } : {};
	}
	const result = existing ? { ...existing } : {};
	const current: SecurityDrawings = result[securityId] ? { ...result[securityId] } : {};

	if (toolType === 'measures') {
		const list: MeasureDrawing[] = [...(current.measures ?? [])];
		const index = drawing.id != null ? list.findIndex((d) => d.id === drawing.id) : -1;
		if (index >= 0) {
			list[index] = drawing as MeasureDrawing;
		} else {
			list.push(drawing as MeasureDrawing);
		}
		current.measures = list;
	} else if (toolType === 'horizontalLines') {
		const list: HorizontalLineDrawing[] = [...(current.horizontalLines ?? [])];
		const index = drawing.id != null ? list.findIndex((d) => d.id === drawing.id) : -1;
		if (index >= 0) {
			list[index] = drawing as HorizontalLineDrawing;
		} else {
			list.push(drawing as HorizontalLineDrawing);
		}
		current.horizontalLines = list;
	} else if (toolType === 'lines') {
		const list: LineDrawing[] = [...(current.lines ?? [])];
		const index = drawing.id != null ? list.findIndex((d) => d.id === drawing.id) : -1;
		if (index >= 0) {
			list[index] = drawing as LineDrawing;
		} else {
			list.push(drawing as LineDrawing);
		}
		current.lines = list;
	}

	result[securityId] = current;
	return result;
}

/**
 * Immutably removes a drawing (by id) from a security + tool type collection,
 * or clears the whole collection when `drawingId` is omitted. Other tool types
 * and other securities are preserved.
 */
export function removeSecurityDrawings(
	existing: SecurityDrawingsMap | null | undefined,
	securityId: string,
	toolType: DrawingToolType,
	drawingId?: string | null
): SecurityDrawingsMap {
	if (!securityId) {
		return existing ? { ...existing } : {};
	}
	const result = existing ? { ...existing } : {};
	const current: SecurityDrawings = result[securityId] ? { ...result[securityId] } : {};

	if (drawingId != null) {
		const list = current[toolType] ?? [];
		const filtered = list.filter((d) => d.id !== drawingId);
		if (toolType === 'measures') {
			current.measures = filtered.length > 0 ? (filtered as MeasureDrawing[]) : null;
		} else if (toolType === 'horizontalLines') {
			current.horizontalLines = filtered.length > 0 ? (filtered as HorizontalLineDrawing[]) : null;
		} else if (toolType === 'lines') {
			current.lines = filtered.length > 0 ? (filtered as LineDrawing[]) : null;
		}
	} else {
		current.measures = toolType === 'measures' ? null : current.measures;
		current.horizontalLines = toolType === 'horizontalLines' ? null : current.horizontalLines;
		current.lines = toolType === 'lines' ? null : current.lines;
	}

	result[securityId] = current;
	return result;
}

/**
 * Returns true when a security has no new-tool drawings at all (null/undefined
 * or every collection empty). Missing collections are treated as empty.
 */
export function isSecurityDrawingsEmpty(value: SecurityDrawings | null | undefined): boolean {
	if (!value) return true;
	const hasEntries = (list: unknown[] | null | undefined): boolean =>
		Array.isArray(list) && list.length > 0;
	return (
		!hasEntries(value.measures) && !hasEntries(value.horizontalLines) && !hasEntries(value.lines)
	);
}

/**
 * Compares two DrawingPoint objects for structural equality (stringifies time
 * so BusinessDay objects and their string forms compare equal).
 */
export function areDrawingPointsEqual(
	a: DrawingPoint | null | undefined,
	b: DrawingPoint | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	return a.price === b.price && String(a.time) === String(b.time);
}

/**
 * Compares two drawings for structural equality (id, points, visibility).
 * Visibility is normalized with `?? true`, so missing (`undefined`) and `true`
 * compare equal. One-point vs two-point drawings with matching p1 compare
 * unequal because of the missing p2.
 */
export function areDrawingsEqual(
	a: Drawing | null | undefined,
	b: Drawing | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;
	if (a.id !== b.id) return false;
	if ((a.visible ?? true) !== (b.visible ?? true)) return false;
	if (!areDrawingPointsEqual(a.p1, b.p1)) return false;

	const aP2 = 'p2' in a ? a.p2 : undefined;
	const bP2 = 'p2' in b ? b.p2 : undefined;
	if (!areDrawingPointsEqual(aP2, bP2)) return false;

	return true;
}

/**
 * Compares two drawing collections order-sensitively, treating null/undefined
 * as empty.
 */
export function areDrawingCollectionsEqual(
	a: Drawing[] | null | undefined,
	b: Drawing[] | null | undefined
): boolean {
	const listA = a ?? [];
	const listB = b ?? [];
	if (listA.length !== listB.length) return false;
	for (let i = 0; i < listA.length; i++) {
		if (!areDrawingsEqual(listA[i], listB[i])) return false;
	}
	return true;
}

/**
 * Compares two SecurityDrawings objects for structural equality, treating
 * missing/null/empty collections as equal.
 */
export function areSecurityDrawingsEqual(
	a: SecurityDrawings | null | undefined,
	b: SecurityDrawings | null | undefined
): boolean {
	if (isSecurityDrawingsEmpty(a) && isSecurityDrawingsEmpty(b)) return true;
	if (!areDrawingCollectionsEqual(a?.measures, b?.measures)) return false;
	if (!areDrawingCollectionsEqual(a?.horizontalLines, b?.horizontalLines)) return false;
	if (!areDrawingCollectionsEqual(a?.lines, b?.lines)) return false;
	return true;
}
