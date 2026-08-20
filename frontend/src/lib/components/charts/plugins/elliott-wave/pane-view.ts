import type {
	IPrimitivePaneRenderer,
	IPrimitivePaneView,
	PrimitivePaneViewZOrder
} from 'lightweight-charts';
import { ElliottWavePaneRenderer, type ElliottWaveRendererData } from './pane-renderer';

export class ElliottWavePaneView implements IPrimitivePaneView {
	private readonly _renderer: ElliottWavePaneRenderer;

	constructor() {
		this._renderer = new ElliottWavePaneRenderer();
	}

	public zOrder(): PrimitivePaneViewZOrder {
		return 'top';
	}

	public renderer(): IPrimitivePaneRenderer {
		return this._renderer;
	}

	public update(data: ElliottWaveRendererData | null): void {
		this._renderer.update(data);
	}
}
