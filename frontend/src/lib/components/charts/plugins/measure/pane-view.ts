import type {
	IPrimitivePaneRenderer,
	IPrimitivePaneView,
	PrimitivePaneViewZOrder
} from 'lightweight-charts';
import { MeasurePaneRenderer, type MeasureRendererData } from './pane-renderer';

export class MeasurePaneView implements IPrimitivePaneView {
	private readonly _renderer: MeasurePaneRenderer;

	constructor() {
		this._renderer = new MeasurePaneRenderer();
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return 'top';
	}

	public renderer(): IPrimitivePaneRenderer {
		return this._renderer;
	}

	public update(data: MeasureRendererData | null): void {
		this._renderer.update(data);
	}
}
