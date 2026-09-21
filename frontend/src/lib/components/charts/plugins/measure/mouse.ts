import type { DrawingPoint } from '$lib/utils/finance/drawings';
import { HIT_TEST_RADIUS } from './constants';
import type { MeasurePointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';
import { pointToSegmentDistance } from '../helpers/mouse/geometry';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedMeasurePointWithTarget {
	id: string;
	pointIndex: 0 | 1;
	x: number;
	y: number;
	originalPoint: DrawingPoint;
}

export interface ProjectedMeasureLine {
	id: string;
	p1: { x: number; y: number };
	p2: { x: number; y: number };
}

/**
 * Thin Measure adapter over the shared {@link ChartMouseHandlers}. Endpoint
 * hit testing is keyed by drawing id + point index. Also supports connecting
 * line segment hit testing.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedMeasurePointWithTarget,
	MeasurePointTarget,
	DrawingPoint
> {
	private _projectedLines: ProjectedMeasureLine[] = [];

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id, pointIndex: p.pointIndex }),
			hitTestLine: (x, y) => this.hitTestLine(x, y)
		});
	}

	public setProjectedLines(lines: ProjectedMeasureLine[]): void {
		this._projectedLines = lines;
	}

	public hitTestLine(x: number, y: number): MeasurePointTarget | null {
		let closestDist = Infinity;
		let closestTarget: MeasurePointTarget | null = null;
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
