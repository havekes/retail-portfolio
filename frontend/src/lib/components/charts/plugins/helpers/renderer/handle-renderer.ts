import { positionsLine } from '../dimensions/positions';
import {
	DEFAULT_DRAG_RING_COLOR,
	DEFAULT_HANDLE_BORDER_COLOR,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_HOVER_RING_COLOR,
	HANDLE_RADIUS
} from './constants';

export interface AnchorHandlePoint {
	x: number;
	y: number;
	isHovered?: boolean;
	isDragging?: boolean;
	isSelected?: boolean;
}

export interface DrawAnchorHandleOptions {
	radius?: number;
	color?: string;
	borderColor?: string;
	borderWidth?: number;
	hoverRingColor?: string;
	dragRingColor?: string;
	ringRadiusOffset?: number;
	ringLineWidth?: number;
	alpha?: number;
}

/**
 * Renders an anchor handle dot on the canvas with high-DPI scaling, crisp 1px
 * pixel-alignment via `positionsLine`, and optional hover/drag highlight rings.
 */
export function drawAnchorHandle(
	ctx: CanvasRenderingContext2D,
	point: AnchorHandlePoint,
	hpr: number,
	vpr: number,
	options?: DrawAnchorHandleOptions
): void {
	const px = positionsLine(point.x, hpr, 1).position;
	const py = positionsLine(point.y, vpr, 1).position;
	const radius = (options?.radius ?? HANDLE_RADIUS) * hpr;
	const color = options?.color ?? DEFAULT_HANDLE_COLOR;
	const borderColor = options?.borderColor ?? DEFAULT_HANDLE_BORDER_COLOR;
	const borderWidth = (options?.borderWidth ?? 1.5) * hpr;
	const hoverRingColor = options?.hoverRingColor ?? DEFAULT_HOVER_RING_COLOR;
	const dragRingColor = options?.dragRingColor ?? DEFAULT_DRAG_RING_COLOR;
	const ringRadiusOffset = (options?.ringRadiusOffset ?? 4) * hpr;
	const ringLineWidth = (options?.ringLineWidth ?? 1.5) * hpr;

	ctx.save();
	try {
		if (options?.alpha !== undefined) {
			ctx.globalAlpha = options.alpha;
		}

		if (point.isHovered || point.isDragging) {
			ctx.save();
			try {
				ctx.beginPath();
				ctx.arc(px, py, radius + ringRadiusOffset, 0, Math.PI * 2);
				ctx.fillStyle = point.isDragging ? dragRingColor : hoverRingColor;
				ctx.fill();
				ctx.lineWidth = ringLineWidth;
				ctx.strokeStyle = color;
				ctx.stroke();
			} finally {
				ctx.restore();
			}
		}

		ctx.save();
		try {
			ctx.beginPath();
			ctx.arc(px, py, radius, 0, Math.PI * 2);
			ctx.fillStyle = color;
			ctx.fill();
			ctx.lineWidth = borderWidth;
			ctx.strokeStyle = borderColor;
			ctx.stroke();
		} finally {
			ctx.restore();
		}
	} finally {
		ctx.restore();
	}
}
