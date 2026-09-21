import { describe, it, expect, beforeEach } from 'vitest';
import { drawAnchorHandle } from './handle-renderer';
import {
	DEFAULT_DRAG_RING_COLOR,
	DEFAULT_HANDLE_BORDER_COLOR,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_HOVER_RING_COLOR,
	HANDLE_RADIUS
} from './constants';
import { positionsLine } from '../dimensions/positions';

interface DrawCall {
	type: string;
	args: unknown[];
	color?: string;
	lineWidth?: number;
}

function createMockContext() {
	const drawCalls: DrawCall[] = [];
	const styles = { strokeStyle: '', fillStyle: '' };

	const context = {
		save() {},
		restore() {},
		beginPath() {},
		arc(...args: unknown[]) {
			drawCalls.push({ type: 'arc', args });
		},
		fill() {
			drawCalls.push({ type: 'fill', args: [], color: styles.fillStyle });
		},
		stroke() {
			drawCalls.push({
				type: 'stroke',
				args: [],
				color: styles.strokeStyle,
				lineWidth: context.lineWidth
			});
		},
		get strokeStyle() {
			return styles.strokeStyle;
		},
		set strokeStyle(value: string) {
			styles.strokeStyle = value;
		},
		get fillStyle() {
			return styles.fillStyle;
		},
		set fillStyle(value: string) {
			styles.fillStyle = value;
		},
		lineWidth: 1,
		globalAlpha: 1
	} as unknown as CanvasRenderingContext2D;

	return { context, drawCalls };
}

describe('drawAnchorHandle', () => {
	let mockCtx: ReturnType<typeof createMockContext>;

	beforeEach(() => {
		mockCtx = createMockContext();
	});

	it('draws a resting handle with 1 arc at pixel-aligned position', () => {
		const point = { x: 100, y: 300 };
		drawAnchorHandle(mockCtx.context, point, 1, 1);

		const arcs = mockCtx.drawCalls.filter((c) => c.type === 'arc');
		expect(arcs).toHaveLength(1);
		const expectedX = positionsLine(100, 1, 1).position;
		const expectedY = positionsLine(300, 1, 1).position;
		expect(arcs[0].args).toEqual([expectedX, expectedY, HANDLE_RADIUS, 0, Math.PI * 2]);

		const fills = mockCtx.drawCalls.filter((c) => c.type === 'fill');
		expect(fills).toHaveLength(1);
		expect(fills[0].color).toBe(DEFAULT_HANDLE_COLOR);

		const strokes = mockCtx.drawCalls.filter((c) => c.type === 'stroke');
		expect(strokes).toHaveLength(1);
		expect(strokes[0].color).toBe(DEFAULT_HANDLE_BORDER_COLOR);
		expect(strokes[0].lineWidth).toBe(1.5);
	});

	it('draws a hover ring before the handle circle (2 arcs)', () => {
		const point = { x: 100, y: 300, isHovered: true };
		drawAnchorHandle(mockCtx.context, point, 1, 1);

		const arcs = mockCtx.drawCalls.filter((c) => c.type === 'arc');
		expect(arcs).toHaveLength(2);

		// Ring first with radius + 4
		expect(arcs[0].args[2]).toBe(HANDLE_RADIUS + 4);
		// Handle circle second with radius
		expect(arcs[1].args[2]).toBe(HANDLE_RADIUS);

		const fills = mockCtx.drawCalls.filter((c) => c.type === 'fill');
		expect(fills).toHaveLength(2);
		expect(fills[0].color).toBe(DEFAULT_HOVER_RING_COLOR);
		expect(fills[1].color).toBe(DEFAULT_HANDLE_COLOR);

		const strokes = mockCtx.drawCalls.filter((c) => c.type === 'stroke');
		expect(strokes).toHaveLength(2);
		expect(strokes[0].color).toBe(DEFAULT_HANDLE_COLOR);
		expect(strokes[1].color).toBe(DEFAULT_HANDLE_BORDER_COLOR);
	});

	it('draws a drag ring with drag ring color when isDragging is true (2 arcs)', () => {
		const point = { x: 100, y: 300, isDragging: true };
		drawAnchorHandle(mockCtx.context, point, 1, 1);

		const arcs = mockCtx.drawCalls.filter((c) => c.type === 'arc');
		expect(arcs).toHaveLength(2);

		const fills = mockCtx.drawCalls.filter((c) => c.type === 'fill');
		expect(fills[0].color).toBe(DEFAULT_DRAG_RING_COLOR);
		expect(fills[1].color).toBe(DEFAULT_HANDLE_COLOR);
	});

	it('applies custom options (radius, colors, stroke widths, alpha)', () => {
		const point = { x: 50, y: 50, isHovered: true };
		drawAnchorHandle(mockCtx.context, point, 1, 1, {
			radius: 8,
			color: '#ff0000',
			borderColor: '#00ff00',
			borderWidth: 2,
			hoverRingColor: 'rgba(255, 0, 0, 0.4)',
			ringRadiusOffset: 6,
			ringLineWidth: 3,
			alpha: 0.5
		});

		expect(mockCtx.context.globalAlpha).toBe(0.5);

		const arcs = mockCtx.drawCalls.filter((c) => c.type === 'arc');
		expect(arcs[0].args[2]).toBe(8 + 6); // ring
		expect(arcs[1].args[2]).toBe(8); // handle

		const fills = mockCtx.drawCalls.filter((c) => c.type === 'fill');
		expect(fills[0].color).toBe('rgba(255, 0, 0, 0.4)');
		expect(fills[1].color).toBe('#ff0000');

		const strokes = mockCtx.drawCalls.filter((c) => c.type === 'stroke');
		expect(strokes[0].lineWidth).toBe(3);
		expect(strokes[0].color).toBe('#ff0000');
		expect(strokes[1].lineWidth).toBe(2);
		expect(strokes[1].color).toBe('#00ff00');
	});

	it('scales coordinates, radius, and line widths correctly under high-DPI (Retina 2x)', () => {
		const point = { x: 100, y: 300, isHovered: true };

		// 1x
		drawAnchorHandle(mockCtx.context, point, 1, 1);
		const calls1x = [...mockCtx.drawCalls];

		// Reset
		mockCtx = createMockContext();

		// 2x
		drawAnchorHandle(mockCtx.context, point, 2, 2);
		const calls2x = [...mockCtx.drawCalls];

		const arcs1x = calls1x.filter((c) => c.type === 'arc');
		const arcs2x = calls2x.filter((c) => c.type === 'arc');

		// 1x positions and radii
		expect(arcs1x[0].args[0]).toBe(positionsLine(100, 1, 1).position);
		expect(arcs1x[0].args[1]).toBe(positionsLine(300, 1, 1).position);
		expect(arcs1x[0].args[2]).toBe(HANDLE_RADIUS + 4);
		expect(arcs1x[1].args[2]).toBe(HANDLE_RADIUS);

		// 2x positions and radii (scaled by 2)
		expect(arcs2x[0].args[0]).toBe(positionsLine(100, 2, 1).position);
		expect(arcs2x[0].args[1]).toBe(positionsLine(300, 2, 1).position);
		expect(arcs2x[0].args[2]).toBe((HANDLE_RADIUS + 4) * 2);
		expect(arcs2x[1].args[2]).toBe(HANDLE_RADIUS * 2);

		// Line widths scaled by 2
		const strokes1x = calls1x.filter((c) => c.type === 'stroke');
		const strokes2x = calls2x.filter((c) => c.type === 'stroke');
		expect(strokes1x[0].lineWidth).toBe(1.5);
		expect(strokes2x[0].lineWidth).toBe(3);
	});
});
