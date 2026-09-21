import { DelegatingPaneView } from '../helpers/primitive/delegating-pane-view';
import { LinePaneRenderer, type LineRendererData } from './pane-renderer';

export class LinePaneView extends DelegatingPaneView<LineRendererData, LinePaneRenderer> {
	constructor() {
		super(new LinePaneRenderer());
	}
}
