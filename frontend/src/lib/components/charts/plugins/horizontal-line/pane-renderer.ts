import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import { positionsBox, positionsLine } from '../helpers/dimensions/positions';
import {
	DEFAULT_DRAG_RING_COLOR,
	DEFAULT_HANDLE_BORDER_COLOR,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_HOVER_RING_COLOR,
	HANDLE_RADIUS,
	HORIZONTAL_LABEL_BG_COLOR,
	HORIZONTAL_LABEL_CHAR_WIDTH,
	HORIZONTAL_LABEL_FONT_SIZE,
	HORIZONTAL_LABEL_HEIGHT,
	HORIZONTAL_LABEL_MARGIN_X,
	HORIZONTAL_LABEL_PADDING_X,
	HORIZONTAL_LABEL_TEXT_COLOR,
	HORIZONTAL_LINE_COLOR,
	HORIZONTAL_LINE_WIDTH,
	PREVIEW_ALPHA,
	PREVIEW_LINE_DASH
} from './constants';

export interface ProjectedHorizontalLinePoint {
	x: number;
	y: number;
	time: Time;
	price: number;
	isHovered?: boolean;
	isDragging?: boolean;
	isSelected?: boolean;
}

export interface HorizontalRenderItem {
	id: string;
	p1: ProjectedHorizontalLinePoint;
	label: string;
	showLabel?: boolean;
	visible?: boolean;
	isSelected?: boolean;
}

export interface HorizontalPreviewData {
	currentMouse: { x: number; y: number; time?: Time | null; price?: number | null } | null;
	label?: string | null;
	showLabel?: boolean;
}

export interface HorizontalRendererData {
	lines: HorizontalRenderItem[];
	preview: HorizontalPreviewData | null;
}

function withSelection(
	point: ProjectedHorizontalLinePoint,
	isSelected?: boolean
): ProjectedHorizontalLinePoint {
	return isSelected ? { ...point, isSelected: true } : point;
}

export class HorizontalLinePaneRenderer implements IPrimitivePaneRenderer {
	private _data: HorizontalRendererData | null = null;

	public update(data: HorizontalRendererData | null): void {
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
				this._drawLine(ctx, scope, item, hpr, vpr);
			}

			if (this._data.preview) {
				this._drawPreview(ctx, scope, this._data.preview, hpr, vpr);
			}
		});
	}

	/** Bitmap x extent (start + length) covering the full media width. */
	private _bitmapSpan(mediaWidth: number, hpr: number) {
		return positionsLine(mediaWidth / 2, hpr, mediaWidth);
	}

	private _drawLine(
		ctx: CanvasRenderingContext2D,
		scope: BitmapCoordinatesRenderingScope,
		item: HorizontalRenderItem,
		hpr: number,
		vpr: number
	): void {
		const xBox = this._bitmapSpan(scope.mediaSize.width, hpr);
		const yBox = positionsLine(item.p1.y, vpr, 1);

		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = HORIZONTAL_LINE_COLOR;
			ctx.lineWidth = HORIZONTAL_LINE_WIDTH * vpr;
			ctx.moveTo(xBox.position, yBox.position);
			ctx.lineTo(xBox.position + xBox.length, yBox.position);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		const showHandle =
			item.isSelected || item.p1.isSelected || item.p1.isHovered || item.p1.isDragging;
		if (showHandle) {
			this._drawHandle(ctx, withSelection(item.p1, item.isSelected), hpr, vpr);
		}

		if (item.showLabel) {
			this._drawLabel(ctx, scope, item.p1, item.label, hpr, vpr);
		}
	}

	private _drawPreview(
		ctx: CanvasRenderingContext2D,
		scope: BitmapCoordinatesRenderingScope,
		preview: HorizontalPreviewData,
		hpr: number,
		vpr: number
	): void {
		const mouse = preview.currentMouse;
		if (!mouse) return;

		const xBox = this._bitmapSpan(scope.mediaSize.width, hpr);
		const yBox = positionsLine(mouse.y, vpr, 1);

		ctx.save();
		try {
			ctx.beginPath();
			ctx.globalAlpha = PREVIEW_ALPHA;
			ctx.strokeStyle = HORIZONTAL_LINE_COLOR;
			ctx.lineWidth = HORIZONTAL_LINE_WIDTH * vpr;
			const dash = PREVIEW_LINE_DASH[0] * hpr;
			ctx.setLineDash([dash, dash]);
			ctx.moveTo(xBox.position, yBox.position);
			ctx.lineTo(xBox.position + xBox.length, yBox.position);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		// Ghost handle at the cursor.
		ctx.save();
		try {
			ctx.globalAlpha = PREVIEW_ALPHA;
			ctx.beginPath();
			ctx.arc(mouse.x * hpr, mouse.y * vpr, HANDLE_RADIUS * hpr, 0, Math.PI * 2);
			ctx.fillStyle = DEFAULT_HANDLE_COLOR;
			ctx.fill();
			ctx.lineWidth = 1.5 * hpr;
			ctx.strokeStyle = DEFAULT_HANDLE_BORDER_COLOR;
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		if (preview.showLabel && preview.label) {
			this._drawLabel(ctx, scope, { x: mouse.x, y: mouse.y }, preview.label, hpr, vpr);
		}
	}

	private _drawHandle(
		ctx: CanvasRenderingContext2D,
		point: ProjectedHorizontalLinePoint,
		hpr: number,
		vpr: number
	): void {
		const px = positionsLine(point.x, hpr, 1).position;
		const py = positionsLine(point.y, vpr, 1).position;
		const radius = HANDLE_RADIUS * hpr;

		if (point.isHovered || point.isDragging) {
			ctx.save();
			try {
				ctx.beginPath();
				ctx.arc(px, py, radius + 4 * hpr, 0, Math.PI * 2);
				ctx.fillStyle = point.isDragging ? DEFAULT_DRAG_RING_COLOR : DEFAULT_HOVER_RING_COLOR;
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

	private _drawLabel(
		ctx: CanvasRenderingContext2D,
		scope: BitmapCoordinatesRenderingScope,
		point: { x: number; y: number },
		text: string,
		hpr: number,
		vpr: number
	): void {
		const textWidth = text.length * HORIZONTAL_LABEL_CHAR_WIDTH + HORIZONTAL_LABEL_PADDING_X * 2;
		const rightEdge = scope.mediaSize.width - HORIZONTAL_LABEL_MARGIN_X;
		const xBox = positionsBox(rightEdge - textWidth, rightEdge, hpr);
		const yBox = positionsLine(point.y, vpr, HORIZONTAL_LABEL_HEIGHT);

		ctx.save();
		try {
			ctx.fillStyle = HORIZONTAL_LABEL_BG_COLOR;
			ctx.fillRect(xBox.position, yBox.position, xBox.length, yBox.length);

			// Accent bar along the bottom edge of the label.
			const accentHeight = Math.max(1, Math.round(hpr));
			ctx.fillStyle = HORIZONTAL_LINE_COLOR;
			ctx.fillRect(
				xBox.position,
				yBox.position + yBox.length - accentHeight,
				xBox.length,
				accentHeight
			);

			ctx.fillStyle = HORIZONTAL_LABEL_TEXT_COLOR;
			ctx.font = `bold ${Math.round(HORIZONTAL_LABEL_FONT_SIZE * vpr)}px sans-serif`;
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(text, xBox.position + xBox.length / 2, yBox.position + yBox.length / 2);
		} finally {
			ctx.restore();
		}
	}
}
