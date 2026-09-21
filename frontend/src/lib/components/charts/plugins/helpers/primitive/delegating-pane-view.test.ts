import { describe, expect, it, vi } from 'vitest';
import { DelegatingPaneView, type IUpdatablePaneRenderer } from './delegating-pane-view';

interface MockData {
	points: number[];
}

class MockRenderer implements IUpdatablePaneRenderer<MockData> {
	public update = vi.fn();
	public draw = vi.fn();
}

describe('DelegatingPaneView', () => {
	it('defaults zOrder to top when omitted', () => {
		const renderer = new MockRenderer();
		const view = new DelegatingPaneView<MockData>(renderer);

		expect(view.zOrder()).toBe('top');
	});

	it('accepts custom zOrder configurations', () => {
		const rendererTop = new MockRenderer();
		const rendererNormal = new MockRenderer();
		const rendererBottom = new MockRenderer();

		const viewTop = new DelegatingPaneView<MockData>(rendererTop, 'top');
		const viewNormal = new DelegatingPaneView<MockData>(rendererNormal, 'normal');
		const viewBottom = new DelegatingPaneView<MockData>(rendererBottom, 'bottom');

		expect(viewTop.zOrder()).toBe('top');
		expect(viewNormal.zOrder()).toBe('normal');
		expect(viewBottom.zOrder()).toBe('bottom');
	});

	it('returns the configured renderer instance', () => {
		const renderer = new MockRenderer();
		const view = new DelegatingPaneView<MockData>(renderer);

		expect(view.renderer()).toBe(renderer);
	});

	it('delegates update calls to the underlying renderer', () => {
		const renderer = new MockRenderer();
		const view = new DelegatingPaneView<MockData>(renderer);

		const data: MockData = { points: [10, 20, 30] };
		view.update(data);
		expect(renderer.update).toHaveBeenCalledTimes(1);
		expect(renderer.update).toHaveBeenCalledWith(data);

		view.update(null);
		expect(renderer.update).toHaveBeenCalledTimes(2);
		expect(renderer.update).toHaveBeenLastCalledWith(null);
	});
});
