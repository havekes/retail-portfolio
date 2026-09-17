import type { DrawingPoint } from '$lib/utils/finance/drawings';
import { HIT_TEST_RADIUS } from './constants';
import type { HorizontalLineTarget } from './state';
import { ChartMouseHandlers } from '../helpers/mouse/chart-mouse-handlers';

export type { MousePosition } from '../helpers/mouse/mouse-position';

export interface ProjectedHorizontalLinePointWithTarget {
	id: string;
	x: number;
	y: number;
	originalPoint: DrawingPoint;
}

/**
 * Thin Horizontal Line adapter over the shared {@link ChartMouseHandlers}.
 * Hit testing is keyed by drawing id only (one handle per line); placement uses
 * the raw click price (no wick snapping), so `adjustPosition` is intentionally
 * omitted.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedHorizontalLinePointWithTarget,
	HorizontalLineTarget,
	DrawingPoint
> {
	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id })
		});
	}
}
