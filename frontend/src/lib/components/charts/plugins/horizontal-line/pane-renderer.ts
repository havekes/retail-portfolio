import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import { positionsLine } from '../helpers/dimensions/positions';
import { drawAnchorHandle, drawChartLabel } from '../helpers/renderer';
import {
	HORIZONTAL_LABEL_MARGIN_X,
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
	isHovered?: boolean;
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
			item.isSelected ||
			item.isHovered ||
			item.p1.isSelected ||
			item.p1.isHovered ||
			item.p1.isDragging;
		if (showHandle) {
			drawAnchorHandle(ctx, withSelection(item.p1, item.isSelected), hpr, vpr);
		}

		if (item.showLabel) {
			drawChartLabel(
				ctx,
				{
					text: item.label,
					x: scope.mediaSize.width - HORIZONTAL_LABEL_MARGIN_X,
					y: item.p1.y,
					align: 'right',
					accentColor: HORIZONTAL_LINE_COLOR
				},
				hpr,
				vpr
			);
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
		drawAnchorHandle(ctx, mouse, hpr, vpr, { alpha: PREVIEW_ALPHA });

		if (preview.showLabel && preview.label) {
			drawChartLabel(
				ctx,
				{
					text: preview.label,
					x: scope.mediaSize.width - HORIZONTAL_LABEL_MARGIN_X,
					y: mouse.y,
					align: 'right',
					accentColor: HORIZONTAL_LINE_COLOR
				},
				hpr,
				vpr
			);
		}
	}
}
