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

export interface ProjectedHorizontalLine {
	id: string;
	y: number;
}

/**
 * Thin Horizontal Line adapter over the shared {@link ChartMouseHandlers}.
 * Hit testing is keyed by drawing id only (one handle per line). Also supports
 * direct line hit testing across the full pane width.
 */
export class MouseHandlers extends ChartMouseHandlers<
	ProjectedHorizontalLinePointWithTarget,
	HorizontalLineTarget,
	DrawingPoint
> {
	private _projectedLines: ProjectedHorizontalLine[] = [];

	constructor() {
		super({
			hitTestRadius: HIT_TEST_RADIUS,
			toTarget: (p) => ({ id: p.id }),
			hitTestLine: (x, y) => this.hitTestLine(x, y)
		});
	}

	public setProjectedLines(lines: ProjectedHorizontalLine[]): void {
		this._projectedLines = lines;
	}

	public hitTestLine(_x: number, y: number): HorizontalLineTarget | null {
		let closestDist = Infinity;
		let closestTarget: HorizontalLineTarget | null = null;
		for (const line of this._projectedLines) {
			const dist = Math.abs(y - line.y);
			if (dist <= HIT_TEST_RADIUS && dist < closestDist) {
				closestDist = dist;
				closestTarget = { id: line.id };
			}
		}
		return closestTarget;
	}
}
