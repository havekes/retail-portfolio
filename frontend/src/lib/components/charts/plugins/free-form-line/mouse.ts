import type { DrawingPoint } from '$lib/utils/finance/drawings';
import { HIT_TEST_RADIUS } from './constants';
import type { LinePointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedLinePointWithTarget {
	id: string;
	pointIndex: 0 | 1;
	x: number;
	y: number;
	originalPoint: DrawingPoint;
}

export interface ProjectedLineSegment {
	id: string;
	p1: { x: number; y: number };
	p2: { x: number; y: number };
}

function pointToSegmentDistance(
	px: number,
	py: number,
	x1: number,
	y1: number,
	x2: number,
	y2: number
): number {
	const dx = x2 - x1;
	const dy = y2 - y1;
	const lenSq = dx * dx + dy * dy;
	if (lenSq === 0) return Math.hypot(px - x1, py - y1);
	const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lenSq));
	return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

/**
 * Free-form Line adapter over the shared {@link ChartMouseHandlers}. Hit testing
 * is keyed by drawing id + point index. Also supports line segment hit testing.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedLinePointWithTarget,
	LinePointTarget,
	DrawingPoint
> {
	private _projectedLines: ProjectedLineSegment[] = [];

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id, pointIndex: p.pointIndex }),
			hitTestLine: (x, y) => this.hitTestLine(x, y)
		});
	}

	public setProjectedLines(lines: ProjectedLineSegment[]): void {
		this._projectedLines = lines;
	}

	public hitTestLine(x: number, y: number): LinePointTarget | null {
		let closestDist = Infinity;
		let closestTarget: LinePointTarget | null = null;
		for (const line of this._projectedLines) {
			const dist = pointToSegmentDistance(x, y, line.p1.x, line.p1.y, line.p2.x, line.p2.y);
			if (dist <= HIT_TEST_RADIUS && dist < closestDist) {
				closestDist = dist;
				closestTarget = { id: line.id, pointIndex: 0 };
			}
		}
		return closestTarget;
	}
}
