import { positionsBox, positionsLine } from '../dimensions/positions';
import {
	DEFAULT_LABEL_BG_COLOR,
	DEFAULT_LABEL_CHAR_WIDTH,
	DEFAULT_LABEL_FONT_SIZE,
	DEFAULT_LABEL_HEIGHT,
	DEFAULT_LABEL_PADDING_X,
	DEFAULT_LABEL_TEXT_COLOR
} from './constants';

export interface ChartLabelConfig {
	text: string;
	x: number;
	y: number;
	align?: 'center' | 'right' | 'left';
	accentColor?: string;
	bgColor?: string;
	textColor?: string;
	height?: number;
	fontSize?: number;
	paddingX?: number;
	charWidth?: number;
}

/**
 * Renders a crisp text label box with optional accent bar, high-DPI scaling,
 * and pixel-alignment via `positionsBox` / `positionsLine`.
 */
export function drawChartLabel(
	ctx: CanvasRenderingContext2D,
	config: ChartLabelConfig,
	hpr: number,
	vpr: number
): void {
	const charWidth = config.charWidth ?? DEFAULT_LABEL_CHAR_WIDTH;
	const paddingX = config.paddingX ?? DEFAULT_LABEL_PADDING_X;
	const height = config.height ?? DEFAULT_LABEL_HEIGHT;
	const fontSize = config.fontSize ?? DEFAULT_LABEL_FONT_SIZE;
	const bgColor = config.bgColor ?? DEFAULT_LABEL_BG_COLOR;
	const textColor = config.textColor ?? DEFAULT_LABEL_TEXT_COLOR;
	const align = config.align ?? 'center';

	const textWidth = config.text.length * charWidth + paddingX * 2;

	let xBox;
	if (align === 'right') {
		xBox = positionsBox(config.x - textWidth, config.x, hpr);
	} else if (align === 'left') {
		xBox = positionsBox(config.x, config.x + textWidth, hpr);
	} else {
		xBox = positionsLine(config.x, hpr, textWidth);
	}

	const yBox = positionsLine(config.y, vpr, height);

	ctx.save();
	try {
		ctx.fillStyle = bgColor;
		ctx.fillRect(xBox.position, yBox.position, xBox.length, yBox.length);

		if (config.accentColor) {
			const accentHeight = Math.max(1, Math.round(hpr));
			ctx.fillStyle = config.accentColor;
			ctx.fillRect(
				xBox.position,
				yBox.position + yBox.length - accentHeight,
				xBox.length,
				accentHeight
			);
		}

		ctx.fillStyle = textColor;
		ctx.font = `bold ${Math.round(fontSize * vpr)}px sans-serif`;
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(config.text, xBox.position + xBox.length / 2, yBox.position + yBox.length / 2);
	} finally {
		ctx.restore();
	}
}
