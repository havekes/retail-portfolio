import type { DrawingPoint } from '$lib/utils/finance/drawings';
import { HIT_TEST_RADIUS } from './constants';
import type { MeasurePointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedMeasurePointWithTarget {
	id: string;
	pointIndex: 0 | 1;
	x: number;
	y: number;
	originalPoint: DrawingPoint;
}

/**
 * Thin Measure adapter over the shared {@link ChartMouseHandlers}. Endpoint
 * hit testing is keyed by drawing id + point index; Measure keeps the raw click
 * position (no wick snapping), so `adjustPosition` is intentionally omitted.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedMeasurePointWithTarget,
	MeasurePointTarget,
	DrawingPoint
> {
	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id, pointIndex: p.pointIndex })
		});
	}
}
