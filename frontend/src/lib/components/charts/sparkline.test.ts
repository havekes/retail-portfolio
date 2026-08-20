import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Sparkline from './sparkline.svelte';
import type { Candle } from '$lib/utils/finance/candle';

describe('Sparkline', () => {
	it('renders SVG with correct default attributes and aria-label', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [10, 20, 15, 25],
				ariaLabel: 'Custom price trend'
			}
		});

		const svg = container.querySelector('svg');
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute('role', 'img');
		expect(svg).toHaveAttribute('aria-label', 'Custom price trend');
		expect(svg).toHaveAttribute('viewBox', '0 0 100 32');
	});

	it('applies emerald green styling (#10b981) when price trend is positive', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [100, 105, 110, 115]
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke', '#10b981');

		const stops = container.querySelectorAll('stop');
		expect(stops[0]).toHaveAttribute('stop-color', '#10b981');
		expect(stops[1]).toHaveAttribute('stop-color', '#10b981');
	});

	it('applies emerald green styling (#10b981) when price trend is flat', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [100, 100, 100]
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke', '#10b981');
	});

	it('applies rose red styling (#f43f5e) when price trend is negative', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [120, 115, 110, 95]
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke', '#f43f5e');

		const stops = container.querySelectorAll('stop');
		expect(stops[0]).toHaveAttribute('stop-color', '#f43f5e');
		expect(stops[1]).toHaveAttribute('stop-color', '#f43f5e');
	});

	it('allows overriding trend styling with isPositive prop', () => {
		// Even though price drops, isPositive=true forces emerald green
		const { container } = render(Sparkline, {
			props: {
				data: [120, 100],
				isPositive: true
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke', '#10b981');
	});

	it('allows custom color override', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [100, 120],
				color: '#3b82f6'
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke', '#3b82f6');

		const stops = container.querySelectorAll('stop');
		expect(stops[0]).toHaveAttribute('stop-color', '#3b82f6');
	});

	it('supports Candle array input data', () => {
		const candles: Candle[] = [
			{ time: '2024-01-01', open: 50, high: 55, low: 48, close: 52 },
			{ time: '2024-01-02', open: 52, high: 58, low: 51, close: 56 },
			{ time: '2024-01-03', open: 56, high: 60, low: 55, close: 59 }
		];

		const { container } = render(Sparkline, {
			props: {
				data: candles
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toBeInTheDocument();
		expect(linePath?.getAttribute('d')).toContain('C'); // smooth bezier curve
		expect(linePath).toHaveAttribute('stroke', '#10b981');
	});

	it('renders area fill gradient with unique gradient id', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [10, 20, 30],
				id: 'custom-sparkline-grad'
			}
		});

		const gradient = container.querySelector('linearGradient');
		expect(gradient).toHaveAttribute('id', 'custom-sparkline-grad');

		const areaPath = container.querySelector('path[fill="url(#custom-sparkline-grad)"]');
		expect(areaPath).toBeInTheDocument();
		expect(areaPath?.getAttribute('d')).toContain('Z'); // closed polygon
	});

	it('hides area fill when showArea is false', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [10, 20, 30],
				id: 'custom-sparkline-grad',
				showArea: false
			}
		});

		const areaPath = container.querySelector('path[fill="url(#custom-sparkline-grad)"]');
		expect(areaPath).not.toBeInTheDocument();
	});

	it('handles empty dataset gracefully without runtime error', () => {
		const { container } = render(Sparkline, {
			props: {
				data: []
			}
		});

		const svg = container.querySelector('svg');
		expect(svg).toBeInTheDocument();

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).not.toBeInTheDocument();
	});

	it('handles single-point dataset gracefully with flat horizontal path', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [42],
				height: 40
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toBeInTheDocument();
		expect(linePath?.getAttribute('d')).not.toContain('NaN');
		expect(linePath?.getAttribute('d')).toBe('M 0 20.00 L 100 20.00');
	});

	it('handles two-point dataset with linear segment', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [10, 20]
			}
		});

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toBeInTheDocument();
		expect(linePath?.getAttribute('d')).toMatch(/^M \d+\.\d+ \d+\.\d+ L \d+\.\d+ \d+\.\d+$/);
	});

	it('applies custom dimensions, strokeWidth, and class', () => {
		const { container } = render(Sparkline, {
			props: {
				data: [10, 20, 30],
				width: 140,
				height: 48,
				strokeWidth: 2.5,
				class: 'my-custom-sparkline'
			}
		});

		const svg = container.querySelector('svg');
		expect(svg).toHaveAttribute('width', '140');
		expect(svg).toHaveAttribute('height', '48');
		expect(svg).toHaveAttribute('viewBox', '0 0 100 48');
		expect(svg?.classList.contains('my-custom-sparkline')).toBe(true);

		const linePath = container.querySelector('path[stroke]');
		expect(linePath).toHaveAttribute('stroke-width', '2.5');
	});
});
