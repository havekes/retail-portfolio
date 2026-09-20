import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import LineIcon from './line-icon.svelte';

describe('LineIcon Component', () => {
	it('renders SVG with diagonal line coordinates (5,19) to (19,5)', () => {
		const { container } = render(LineIcon, {
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
		expect(line?.getAttribute('x1')).toBe('5');
		expect(line?.getAttribute('y1')).toBe('19');
		expect(line?.getAttribute('x2')).toBe('19');
		expect(line?.getAttribute('y2')).toBe('5');
	});
});
