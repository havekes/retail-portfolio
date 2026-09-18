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

/**
 * Thin free-form line adapter over the shared {@link ChartMouseHandlers}.
 * Endpoint hit testing is keyed by drawing id + point index; the tool keeps the
 * raw click position (no wick snapping), so `adjustPosition` is intentionally
 * omitted.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedLinePointWithTarget,
	LinePointTarget,
	DrawingPoint
> {
	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id, pointIndex: p.pointIndex })
		});
	}
}
