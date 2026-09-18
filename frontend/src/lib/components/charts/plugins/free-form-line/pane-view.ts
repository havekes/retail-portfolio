import type {
	IPrimitivePaneRenderer,
	IPrimitivePaneView,
	PrimitivePaneViewZOrder
} from 'lightweight-charts';
import { LinePaneRenderer, type LineRendererData } from './pane-renderer';

export class LinePaneView implements IPrimitivePaneView {
	private readonly _renderer: LinePaneRenderer;

	constructor() {
		this._renderer = new LinePaneRenderer();
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return 'top';
	}

	public renderer(): IPrimitivePaneRenderer {
		return this._renderer;
	}

	public update(data: LineRendererData | null): void {
		this._renderer.update(data);
	}
}
