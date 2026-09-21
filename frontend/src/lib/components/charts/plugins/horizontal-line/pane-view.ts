import { DelegatingPaneView } from '../helpers/primitive/delegating-pane-view';
import { HorizontalLinePaneRenderer, type HorizontalRendererData } from './pane-renderer';

export class HorizontalLinePaneView extends DelegatingPaneView<
	HorizontalRendererData,
	HorizontalLinePaneRenderer
> {
	constructor() {
		super(new HorizontalLinePaneRenderer());
	}
}
