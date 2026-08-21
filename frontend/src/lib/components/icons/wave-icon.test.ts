import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import WaveIcon from './wave-icon.svelte';

describe('WaveIcon Component', () => {
	it('renders SVG with 5-wave Elliott impulse path', () => {
		const { container } = render(WaveIcon, { props: { size: 24, class: 'test-class' } });
		const svg = container.querySelector('svg');
		expect(svg).toBeInTheDocument();
		expect(svg?.getAttribute('width')).toBe('24');
		expect(svg?.getAttribute('height')).toBe('24');
		expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
		expect(svg?.getAttribute('class')).toContain('test-class');

		const path = svg?.querySelector('path');
		expect(path).toBeInTheDocument();
		expect(path?.getAttribute('d')).toBe('M2 20 L6 13 L10 16 L15 7 L18 10 L22 4');
	});
});
