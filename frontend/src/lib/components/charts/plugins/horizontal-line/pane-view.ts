import type {
	IPrimitivePaneRenderer,
	IPrimitivePaneView,
	PrimitivePaneViewZOrder
} from 'lightweight-charts';
import { HorizontalLinePaneRenderer, type HorizontalRendererData } from './pane-renderer';

export class HorizontalLinePaneView implements IPrimitivePaneView {
	private readonly _renderer: HorizontalLinePaneRenderer;

	constructor() {
		this._renderer = new HorizontalLinePaneRenderer();
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return 'top';
	}

	public renderer(): IPrimitivePaneRenderer {
		return this._renderer;
	}

	public update(data: HorizontalRendererData | null): void {
		this._renderer.update(data);
	}
}
