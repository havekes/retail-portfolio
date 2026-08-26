import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CorrectiveWaveIcon from './corrective-wave-icon.svelte';

describe('CorrectiveWaveIcon Component', () => {
	it('renders SVG with 3-segment Elliott corrective path (0, A, B, C)', () => {
		const { container } = render(CorrectiveWaveIcon, { props: { size: 24, class: 'test-class' } });
		const svg = container.querySelector('svg');
		expect(svg).toBeInTheDocument();
		expect(svg?.getAttribute('width')).toBe('24');
		expect(svg?.getAttribute('height')).toBe('24');
		expect(svg?.getAttribute('viewBox')).toBe('0 0 24 24');
		expect(svg?.getAttribute('class')).toContain('test-class');

		const path = svg?.querySelector('path');
		expect(path).toBeInTheDocument();
		expect(path?.getAttribute('d')).toBe('M3 6 L9 18 L15 10 L21 20');
	});
});
