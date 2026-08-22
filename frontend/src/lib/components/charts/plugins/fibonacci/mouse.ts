import type { FibPoint, FibToolType } from '$lib/utils/finance/fibonacci';
import { HIT_TEST_RADIUS } from './constants';
import type { FibPointTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedFibPointWithTarget {
	tool: FibToolType;
	pointIndex: 0 | 1 | 2;
	x: number;
	y: number;
	originalPoint: FibPoint;
}

/**
 * Thin fibonacci adapter over the shared {@link ChartMouseHandlers}. Keeps the
 * plugin's public `MouseHandlers` surface (zero-arg constructor included);
 * hit-testing and all event plumbing live in the shared handler.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedFibPointWithTarget,
	FibPointTarget,
	FibPoint
> {
	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ tool: p.tool, pointIndex: p.pointIndex })
		});
	}
}
