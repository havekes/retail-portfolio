import type { IPrimitivePaneRenderer, PrimitivePaneViewZOrder } from 'lightweight-charts';
import type { IUpdatablePaneView } from './drawing-primitive-base';

export type { IUpdatablePaneView };

/**
 * Renderer contract supporting dynamic data updates from the primitive lifecycle.
 */
export interface IUpdatablePaneRenderer<TRendererData> extends IPrimitivePaneRenderer {
	update(data: TRendererData | null): void;
}

/**
 * Reusable pane view delegating rendering to an underlying updatable renderer.
 * Eliminates boilerplate across drawing tools whose pane view merely holds a
 * renderer and forwards updates.
 */
export class DelegatingPaneView<
	TRendererData,
	TRenderer extends IUpdatablePaneRenderer<TRendererData> = IUpdatablePaneRenderer<TRendererData>
> implements IUpdatablePaneView<TRendererData> {
	protected readonly _renderer: TRenderer;
	protected readonly _zOrder: PrimitivePaneViewZOrder;

	constructor(renderer: TRenderer, zOrder: PrimitivePaneViewZOrder = 'top') {
		this._renderer = renderer;
		this._zOrder = zOrder;
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return this._zOrder;
	}

	public renderer(): TRenderer {
		return this._renderer;
	}

	public update(data: TRendererData | null): void {
		this._renderer.update(data);
	}
}
