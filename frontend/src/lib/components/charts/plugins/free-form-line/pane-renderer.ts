import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import { positionsLine } from '../helpers/dimensions/positions';
import {
	DEFAULT_DRAG_RING_COLOR,
	DEFAULT_HANDLE_BORDER_COLOR,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_HOVER_RING_COLOR,
	DEFAULT_SELECTED_RING_COLOR,
	FREE_FORM_LINE_COLOR,
	FREE_FORM_LINE_WIDTH,
	HANDLE_RADIUS,
	PREVIEW_ALPHA,
	PREVIEW_LINE_DASH
} from './constants';

export interface ProjectedLinePoint {
	pointIndex: 0 | 1;
	x: number;
	y: number;
	time: Time;
	price: number;
	isHovered?: boolean;
	isDragging?: boolean;
	isSelected?: boolean;
}

export interface LineRenderItem {
	id: string;
	p1: ProjectedLinePoint;
	p2: ProjectedLinePoint;
	visible?: boolean;
	isSelected?: boolean;
}

export interface LinePreviewData {
	placedPoints: ProjectedLinePoint[];
	currentMouse: { x: number; y: number; time?: Time | null; price?: number | null } | null;
}

export interface LineRendererData {
	lines: LineRenderItem[];
	preview: LinePreviewData | null;
}

function withSelection(point: ProjectedLinePoint, isSelected?: boolean): ProjectedLinePoint {
	return isSelected ? { ...point, isSelected: true } : point;
}

/**
 * Renderer for the free-form line tool. Draws a plain straight segment between
 * the two anchors plus a draggable dot handle at each endpoint; while the first
 * point is pending a dashed translucent segment follows the cursor together
 * with a ghost handle.
 */
export class LinePaneRenderer implements IPrimitivePaneRenderer {
	private _data: LineRendererData | null = null;

	public update(data: LineRendererData | null): void {
		this._data = data;
	}

	public draw(target: CanvasRenderingTarget2D): void {
		target.useBitmapCoordinateSpace((scope: BitmapCoordinatesRenderingScope) => {
			if (!this._data) return;
			const ctx = scope.context;
			const hpr = scope.horizontalPixelRatio;
			const vpr = scope.verticalPixelRatio;

			for (const item of this._data.lines) {
				if (item.visible === false) continue;
				this._drawLine(ctx, item, hpr, vpr);
			}

			if (this._data.preview) {
				this._drawPreview(ctx, this._data.preview, hpr, vpr);
			}
		});
	}

	private _drawLine(
		ctx: CanvasRenderingContext2D,
		item: LineRenderItem,
		hpr: number,
		vpr: number
	): void {
		const x1 = item.p1.x * hpr;
		const y1 = item.p1.y * vpr;
		const x2 = item.p2.x * hpr;
		const y2 = item.p2.y * vpr;

		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = FREE_FORM_LINE_COLOR;
			ctx.lineWidth = FREE_FORM_LINE_WIDTH * hpr;
			ctx.moveTo(x1, y1);
			ctx.lineTo(x2, y2);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		this._drawHandle(ctx, withSelection(item.p1, item.isSelected), hpr, vpr);
		this._drawHandle(ctx, withSelection(item.p2, item.isSelected), hpr, vpr);
	}

	private _drawPreview(
		ctx: CanvasRenderingContext2D,
		preview: LinePreviewData,
		hpr: number,
		vpr: number
	): void {
		for (const point of preview.placedPoints) {
			this._drawHandle(ctx, point, hpr, vpr);
		}

		const mouse = preview.currentMouse;
		if (!mouse) return;

		const mouseX = mouse.x * hpr;
		const mouseY = mouse.y * vpr;
		const anchor = preview.placedPoints[0];

		if (anchor) {
			ctx.save();
			try {
				ctx.beginPath();
				ctx.globalAlpha = PREVIEW_ALPHA;
				ctx.strokeStyle = FREE_FORM_LINE_COLOR;
				ctx.lineWidth = FREE_FORM_LINE_WIDTH * hpr;
				const dash = PREVIEW_LINE_DASH[0] * hpr;
				ctx.setLineDash([dash, dash]);
				ctx.moveTo(anchor.x * hpr, anchor.y * vpr);
				ctx.lineTo(mouseX, mouseY);
				ctx.stroke();
			} finally {
				ctx.restore();
			}
		}

		// Ghost handle at the cursor.
		ctx.save();
		try {
			ctx.globalAlpha = PREVIEW_ALPHA;
			ctx.beginPath();
			ctx.arc(mouseX, mouseY, HANDLE_RADIUS * hpr, 0, Math.PI * 2);
			ctx.fillStyle = DEFAULT_HANDLE_COLOR;
			ctx.fill();
			ctx.lineWidth = 1.5 * hpr;
			ctx.strokeStyle = DEFAULT_HANDLE_BORDER_COLOR;
			ctx.stroke();
		} finally {
			ctx.restore();
		}
	}

	private _drawHandle(
		ctx: CanvasRenderingContext2D,
		point: ProjectedLinePoint,
		hpr: number,
		vpr: number
	): void {
		const px = positionsLine(point.x, hpr, 1).position;
		const py = positionsLine(point.y, vpr, 1).position;
		const radius = HANDLE_RADIUS * hpr;

		if (point.isHovered || point.isDragging || point.isSelected) {
			ctx.save();
			try {
				ctx.beginPath();
				ctx.arc(px, py, radius + 4 * hpr, 0, Math.PI * 2);
				ctx.fillStyle = point.isDragging
					? DEFAULT_DRAG_RING_COLOR
					: point.isHovered
						? DEFAULT_HOVER_RING_COLOR
						: DEFAULT_SELECTED_RING_COLOR;
				ctx.fill();
				ctx.lineWidth = 1.5 * hpr;
				ctx.strokeStyle = DEFAULT_HANDLE_COLOR;
				ctx.stroke();
			} finally {
				ctx.restore();
			}
		}

		ctx.save();
		try {
			ctx.beginPath();
			ctx.arc(px, py, radius, 0, Math.PI * 2);
			ctx.fillStyle = DEFAULT_HANDLE_COLOR;
			ctx.fill();
			ctx.lineWidth = 1.5 * hpr;
			ctx.strokeStyle = DEFAULT_HANDLE_BORDER_COLOR;
			ctx.stroke();
		} finally {
			ctx.restore();
		}
	}
}
