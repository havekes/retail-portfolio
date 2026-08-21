import type {
	IPrimitivePaneRenderer,
	IPrimitivePaneView,
	PrimitivePaneViewZOrder
} from 'lightweight-charts';
import { FibonacciPaneRenderer, type FibonacciRendererData } from './pane-renderer';

export class FibonacciPaneView implements IPrimitivePaneView {
	private readonly _renderer: FibonacciPaneRenderer;

	constructor() {
		this._renderer = new FibonacciPaneRenderer();
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return 'top';
	}

	public renderer(): IPrimitivePaneRenderer {
		return this._renderer;
	}

	public update(data: FibonacciRendererData | null): void {
		this._renderer.update(data);
	}
}
