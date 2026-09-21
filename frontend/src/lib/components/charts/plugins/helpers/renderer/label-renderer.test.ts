import { describe, it, expect, beforeEach } from 'vitest';
import { drawChartLabel } from './label-renderer';
import {
	DEFAULT_LABEL_BG_COLOR,
	DEFAULT_LABEL_CHAR_WIDTH,
	DEFAULT_LABEL_FONT_SIZE,
	DEFAULT_LABEL_HEIGHT,
	DEFAULT_LABEL_PADDING_X,
	DEFAULT_LABEL_TEXT_COLOR
} from './constants';
import { positionsBox, positionsLine } from '../dimensions/positions';

interface DrawCall {
	type: string;
	args: unknown[];
	color?: string;
}

function createMockContext() {
	const drawCalls: DrawCall[] = [];
	const styles = { strokeStyle: '', fillStyle: '' };

	const context = {
		save() {},
		restore() {},
		fillRect(...args: unknown[]) {
			drawCalls.push({ type: 'fillRect', args, color: styles.fillStyle });
		},
		fillText(text: string, x: number, y: number) {
			drawCalls.push({ type: 'fillText', args: [text, x, y] });
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
		font: '',
		textAlign: 'start',
		textBaseline: 'alphabetic'
	} as unknown as CanvasRenderingContext2D;

	return { context, drawCalls };
}

describe('drawChartLabel', () => {
	let mockCtx: ReturnType<typeof createMockContext>;

	beforeEach(() => {
		mockCtx = createMockContext();
	});

	it('renders a centered label with background fillRect and centered fillText', () => {
		const text = '+12.50 (+5.2%)';
		drawChartLabel(mockCtx.context, { text, x: 200, y: 150 }, 1, 1);

		const rects = mockCtx.drawCalls.filter((c) => c.type === 'fillRect');
		expect(rects).toHaveLength(1);
		expect(rects[0].color).toBe(DEFAULT_LABEL_BG_COLOR);

		const textWidth = text.length * DEFAULT_LABEL_CHAR_WIDTH + DEFAULT_LABEL_PADDING_X * 2;
		const expectedXBox = positionsLine(200, 1, textWidth);
		const expectedYBox = positionsLine(150, 1, DEFAULT_LABEL_HEIGHT);
		expect(rects[0].args).toEqual([
			expectedXBox.position,
			expectedYBox.position,
			expectedXBox.length,
			expectedYBox.length
		]);

		const texts = mockCtx.drawCalls.filter((c) => c.type === 'fillText');
		expect(texts).toHaveLength(1);
		expect(texts[0].args[0]).toBe(text);
		expect(texts[0].args[1]).toBe(expectedXBox.position + expectedXBox.length / 2);
		expect(texts[0].args[2]).toBe(expectedYBox.position + expectedYBox.length / 2);
		expect(mockCtx.context.font).toBe(`bold ${DEFAULT_LABEL_FONT_SIZE}px sans-serif`);
		expect(mockCtx.context.textAlign).toBe('center');
		expect(mockCtx.context.textBaseline).toBe('middle');
		expect(mockCtx.context.fillStyle).toBe(DEFAULT_LABEL_TEXT_COLOR);
	});

	it('renders a right-aligned label using positionsBox', () => {
		const text = '145.00';
		const rightEdge = 792;
		drawChartLabel(mockCtx.context, { text, x: rightEdge, y: 100, align: 'right' }, 1, 1);

		const rects = mockCtx.drawCalls.filter((c) => c.type === 'fillRect');
		expect(rects).toHaveLength(1);

		const textWidth = text.length * DEFAULT_LABEL_CHAR_WIDTH + DEFAULT_LABEL_PADDING_X * 2;
		const expectedXBox = positionsBox(rightEdge - textWidth, rightEdge, 1);
		expect(rects[0].args[0]).toBe(expectedXBox.position);
		expect(rects[0].args[2]).toBe(expectedXBox.length);
	});

	it('renders a left-aligned label using positionsBox', () => {
		const text = '145.00';
		const leftEdge = 10;
		drawChartLabel(mockCtx.context, { text, x: leftEdge, y: 100, align: 'left' }, 1, 1);

		const rects = mockCtx.drawCalls.filter((c) => c.type === 'fillRect');
		expect(rects).toHaveLength(1);

		const textWidth = text.length * DEFAULT_LABEL_CHAR_WIDTH + DEFAULT_LABEL_PADDING_X * 2;
		const expectedXBox = positionsBox(leftEdge, leftEdge + textWidth, 1);
		expect(rects[0].args[0]).toBe(expectedXBox.position);
		expect(rects[0].args[2]).toBe(expectedXBox.length);
	});

	it('renders an accent bar along the bottom edge when accentColor is provided', () => {
		const text = '145.00';
		const accentColor = '#2962FF';
		drawChartLabel(mockCtx.context, { text, x: 200, y: 100, align: 'center', accentColor }, 1, 1);

		const rects = mockCtx.drawCalls.filter((c) => c.type === 'fillRect');
		expect(rects).toHaveLength(2); // bg + accent bar

		// First is background
		expect(rects[0].color).toBe(DEFAULT_LABEL_BG_COLOR);

		// Second is accent bar
		expect(rects[1].color).toBe(accentColor);
		const textWidth = text.length * DEFAULT_LABEL_CHAR_WIDTH + DEFAULT_LABEL_PADDING_X * 2;
		const xBox = positionsLine(200, 1, textWidth);
		const yBox = positionsLine(100, 1, DEFAULT_LABEL_HEIGHT);
		const accentHeight = 1;
		expect(rects[1].args).toEqual([
			xBox.position,
			yBox.position + yBox.length - accentHeight,
			xBox.length,
			accentHeight
		]);
	});

	it('scales font size and accent bar under high-DPI (Retina 2x)', () => {
		const text = '145.00';
		const accentColor = '#089981';

		// 1x
		drawChartLabel(mockCtx.context, { text, x: 200, y: 100, align: 'center', accentColor }, 1, 1);
		const calls1x = [...mockCtx.drawCalls];
		const font1x = mockCtx.context.font;

		// 2x
		mockCtx = createMockContext();
		drawChartLabel(mockCtx.context, { text, x: 200, y: 100, align: 'center', accentColor }, 2, 2);
		const calls2x = [...mockCtx.drawCalls];
		const font2x = mockCtx.context.font;

		expect(font1x).toBe(`bold ${DEFAULT_LABEL_FONT_SIZE}px sans-serif`);
		expect(font2x).toBe(`bold ${DEFAULT_LABEL_FONT_SIZE * 2}px sans-serif`);

		// Accent bar height scaled at 2x
		const accent1x = calls1x.filter((c) => c.type === 'fillRect')[1];
		const accent2x = calls2x.filter((c) => c.type === 'fillRect')[1];
		expect(accent1x.args[3]).toBe(1);
		expect(accent2x.args[3]).toBe(2);
	});

	it('supports custom styling options', () => {
		drawChartLabel(
			mockCtx.context,
			{
				text: 'Custom',
				x: 100,
				y: 50,
				bgColor: '#333333',
				textColor: '#ffff00',
				height: 24,
				fontSize: 14,
				paddingX: 10,
				charWidth: 8
			},
			1,
			1
		);

		const rects = mockCtx.drawCalls.filter((c) => c.type === 'fillRect');
		expect(rects[0].color).toBe('#333333');
		expect(mockCtx.context.font).toBe('bold 14px sans-serif');
		expect(mockCtx.context.fillStyle).toBe('#ffff00');
	});
});
