import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import HorizontalLineIcon from './horizontal-line-icon.svelte';

describe('HorizontalLineIcon Component', () => {
	it('renders SVG with horizontal line coordinates (3,12) to (21,12)', () => {
		const { container } = render(HorizontalLineIcon, {
			props: { size: 24, class: 'test-class' }
		});
		const svg = container.querySelector('svg');
		expect(svg).toBeInTheDocument();
		expect(svg?.getAttribute('width')).toBe('24');
		expect(svg?.getAttribute('height')).toBe('24');
		expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
		expect(svg?.getAttribute('class')).toContain('test-class');

		const line = svg?.querySelector('line');
		expect(line).toBeInTheDocument();
		expect(line?.getAttribute('x1')).toBe('3');
		expect(line?.getAttribute('y1')).toBe('12');
		expect(line?.getAttribute('x2')).toBe('21');
		expect(line?.getAttribute('y2')).toBe('12');
	});
});
