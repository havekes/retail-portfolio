import { DelegatingPaneView } from '../helpers/primitive/delegating-pane-view';
import { MeasurePaneRenderer, type MeasureRendererData } from './pane-renderer';

export class MeasurePaneView extends DelegatingPaneView<MeasureRendererData, MeasurePaneRenderer> {
	constructor() {
		super(new MeasurePaneRenderer());
	}
}
