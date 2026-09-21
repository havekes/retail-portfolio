import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import type { MeasureDirection } from '$lib/utils/finance/measure';
import { drawAnchorHandle, drawChartLabel } from '../helpers/renderer';
import {
	MEASURE_FILL_ALPHA,
	MEASURE_LINE_WIDTH,
	PREVIEW_ALPHA,
	PREVIEW_LINE_DASH,
	measureColor
} from './constants';

export interface ProjectedMeasurePoint {
	pointIndex: 0 | 1;
	x: number;
	y: number;
	time: Time;
	price: number;
	isHovered?: boolean;
	isDragging?: boolean;
	isSelected?: boolean;
}

export interface MeasureRenderItem {
	id: string;
	p1: ProjectedMeasurePoint;
	p2: ProjectedMeasurePoint;
	delta: number;
	percent: number;
	direction: MeasureDirection;
	label: string;
	visible?: boolean;
	isSelected?: boolean;
	isHovered?: boolean;
}

export interface MeasurePreviewData {
	placedPoints: ProjectedMeasurePoint[];
	currentMouse: { x: number; y: number; time?: Time | null; price?: number | null } | null;
	label?: string | null;
	direction?: MeasureDirection | null;
}

export interface MeasureRendererData {
	measures: MeasureRenderItem[];
	preview: MeasurePreviewData | null;
}

function withSelection(point: ProjectedMeasurePoint, isSelected?: boolean): ProjectedMeasurePoint {
	return isSelected ? { ...point, isSelected: true } : point;
}

export class MeasurePaneRenderer implements IPrimitivePaneRenderer {
	private _data: MeasureRendererData | null = null;

	public update(data: MeasureRendererData | null): void {
		this._data = data;
	}

	public draw(target: CanvasRenderingTarget2D): void {
		target.useBitmapCoordinateSpace((scope: BitmapCoordinatesRenderingScope) => {
			if (!this._data) return;
			const ctx = scope.context;
			const hpr = scope.horizontalPixelRatio;
			const vpr = scope.verticalPixelRatio;

			for (const item of this._data.measures) {
				if (item.visible === false) continue;
				this._drawMeasure(ctx, item, hpr, vpr);
			}

			if (this._data.preview) {
				this._drawPreview(ctx, this._data.preview, hpr, vpr);
			}
		});
	}

	private _drawMeasure(
		ctx: CanvasRenderingContext2D,
		item: MeasureRenderItem,
		hpr: number,
		vpr: number
	): void {
		const color = measureColor(item.direction);
		const x1 = item.p1.x * hpr;
		const y1 = item.p1.y * vpr;
		const x2 = item.p2.x * hpr;
		const y2 = item.p2.y * vpr;

		// Translucent range shading between the two anchors.
		ctx.save();
		try {
			ctx.globalAlpha = MEASURE_FILL_ALPHA;
			ctx.fillStyle = color;
			ctx.fillRect(
				Math.min(x1, x2),
				Math.min(y1, y2),
				Math.max(1, Math.abs(x2 - x1)),
				Math.max(1, Math.abs(y2 - y1))
			);
		} finally {
			ctx.restore();
		}

		// Connecting line.
		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = color;
			ctx.lineWidth = MEASURE_LINE_WIDTH * hpr;
			ctx.moveTo(x1, y1);
			ctx.lineTo(x2, y2);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		// Directional arrowhead at endpoint p2 oriented along segment vector.
		this._drawArrowhead(ctx, x1, y1, x2, y2, color, hpr);

		const showHandles =
			item.isSelected ||
			item.isHovered ||
			item.p1.isSelected ||
			item.p2.isSelected ||
			item.p1.isHovered ||
			item.p1.isDragging ||
			item.p2.isHovered ||
			item.p2.isDragging;

		if (showHandles) {
			drawAnchorHandle(ctx, withSelection(item.p1, item.isSelected), hpr, vpr);
			drawAnchorHandle(ctx, withSelection(item.p2, item.isSelected), hpr, vpr);
		}

		drawChartLabel(
			ctx,
			{
				text: item.label,
				x: (item.p1.x + item.p2.x) / 2,
				y: (item.p1.y + item.p2.y) / 2,
				align: 'center',
				accentColor: color
			},
			hpr,
			vpr
		);
	}

	private _drawArrowhead(
		ctx: CanvasRenderingContext2D,
		fromX: number,
		fromY: number,
		toX: number,
		toY: number,
		color: string,
		hpr: number
	): void {
		const dx = toX - fromX;
		const dy = toY - fromY;
		const len = Math.hypot(dx, dy);
		if (len === 0) return;

		const angle = Math.atan2(dy, dx);
		const arrowLength = 10 * hpr;
		const arrowAngle = Math.PI / 6;

		ctx.save();
		try {
			ctx.beginPath();
			ctx.fillStyle = color;
			ctx.moveTo(toX, toY);
			ctx.lineTo(
				toX - arrowLength * Math.cos(angle - arrowAngle),
				toY - arrowLength * Math.sin(angle - arrowAngle)
			);
			ctx.lineTo(
				toX - arrowLength * Math.cos(angle + arrowAngle),
				toY - arrowLength * Math.sin(angle + arrowAngle)
			);
			ctx.closePath();
			ctx.fill();
		} finally {
			ctx.restore();
		}
	}

	private _drawPreview(
		ctx: CanvasRenderingContext2D,
		preview: MeasurePreviewData,
		hpr: number,
		vpr: number
	): void {
		for (const point of preview.placedPoints) {
			drawAnchorHandle(ctx, point, hpr, vpr);
		}

		const mouse = preview.currentMouse;
		if (!mouse) return;

		const mouseX = mouse.x * hpr;
		const mouseY = mouse.y * vpr;
		const anchor = preview.placedPoints[0];

		if (anchor) {
			const color = measureColor(preview.direction ?? 'flat');
			ctx.save();
			try {
				ctx.beginPath();
				ctx.globalAlpha = PREVIEW_ALPHA;
				ctx.strokeStyle = color;
				ctx.lineWidth = MEASURE_LINE_WIDTH * hpr;
				const dash = PREVIEW_LINE_DASH[0] * hpr;
				ctx.setLineDash([dash, dash]);
				ctx.moveTo(anchor.x * hpr, anchor.y * vpr);
				ctx.lineTo(mouseX, mouseY);
				ctx.stroke();
			} finally {
				ctx.restore();
			}

			this._drawArrowhead(ctx, anchor.x * hpr, anchor.y * vpr, mouseX, mouseY, color, hpr);
		}

		// Ghost anchor handle at the cursor.
		drawAnchorHandle(ctx, mouse, hpr, vpr, { alpha: PREVIEW_ALPHA });

		if (anchor && preview.label) {
			drawChartLabel(
				ctx,
				{
					text: preview.label,
					x: (anchor.x + mouse.x) / 2,
					y: (anchor.y + mouse.y) / 2,
					align: 'center',
					accentColor: measureColor(preview.direction ?? 'flat')
				},
				hpr,
				vpr
			);
		}
	}
}
