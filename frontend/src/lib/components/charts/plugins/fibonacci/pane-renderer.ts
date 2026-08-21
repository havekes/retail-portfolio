import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import type { FibToolType } from '$lib/utils/finance/fibonacci';
import {
	DEFAULT_DRAG_RING_COLOR,
	DEFAULT_HANDLE_BORDER_COLOR,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_HOVER_RING_COLOR,
	DEFAULT_LEVEL_LINE_DASH,
	DEFAULT_LEVEL_LINE_WIDTH,
	DEFAULT_SELECTED_RING_COLOR,
	DEFAULT_TRENDLINE_COLOR,
	DEFAULT_TRENDLINE_WIDTH,
	HANDLE_RADIUS,
	PREVIEW_ALPHA,
	PREVIEW_LINE_DASH
} from './constants';

export interface ProjectedFibPoint {
	pointIndex: 0 | 1 | 2;
	x: number;
	y: number;
	time: Time;
	price: number;
	isHovered?: boolean;
	isDragging?: boolean;
	isSelected?: boolean;
}

export interface ProjectedFibLevel {
	ratio: number;
	price: number;
	y: number;
	formattedPrice: string;
	label: string;
	color?: string;
	enabled?: boolean;
}

export interface RetracementRenderData {
	p1: ProjectedFibPoint;
	p2: ProjectedFibPoint;
	levels: ProjectedFibLevel[];
	extendLines?: boolean;
	visible?: boolean;
	isSelected?: boolean;
}

export interface ExtensionRenderData {
	p1: ProjectedFibPoint;
	p2: ProjectedFibPoint;
	p3: ProjectedFibPoint;
	levels: ProjectedFibLevel[];
	extendLines?: boolean;
	visible?: boolean;
	isSelected?: boolean;
}

export interface FibDrawingPreviewData {
	tool: FibToolType;
	placedPoints: ProjectedFibPoint[];
	currentMouse: { x: number; y: number; time?: Time | null; price?: number | null } | null;
	previewLevels?: ProjectedFibLevel[];
}

export interface FibonacciRendererData {
	retracement: RetracementRenderData | null;
	extension: ExtensionRenderData | null;
	preview: FibDrawingPreviewData | null;
}

export class FibonacciPaneRenderer implements IPrimitivePaneRenderer {
	private _data: FibonacciRendererData | null = null;

	public update(data: FibonacciRendererData | null): void {
		this._data = data;
	}

	public draw(target: CanvasRenderingTarget2D): void {
		target.useBitmapCoordinateSpace((scope: BitmapCoordinatesRenderingScope) => {
			if (!this._data) return;
			const ctx = scope.context;
			const hpr = scope.horizontalPixelRatio;
			const vpr = scope.verticalPixelRatio;
			const width = scope.mediaSize.width;

			// 1. Draw live preview while in drawing mode
			if (this._data.preview && this._data.preview.currentMouse) {
				this._drawDrawingPreview(ctx, this._data.preview, hpr, vpr);
			}

			// 2. Draw placed Retracement
			if (this._data.retracement && this._data.retracement.visible !== false) {
				this._drawRetracement(ctx, this._data.retracement, hpr, vpr, width);
			}

			// 3. Draw placed Extension
			if (this._data.extension && this._data.extension.visible !== false) {
				this._drawExtension(ctx, this._data.extension, hpr, vpr, width);
			}
		});
	}

	private _drawRetracement(
		ctx: CanvasRenderingContext2D,
		data: RetracementRenderData,
		hpr: number,
		vpr: number,
		width: number
	): void {
		const { p1, p2, levels, extendLines } = data;

		// 1. Trendline connecting p1 to p2
		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = DEFAULT_TRENDLINE_COLOR;
			ctx.lineWidth = DEFAULT_TRENDLINE_WIDTH * hpr;
			const dash = 3 * hpr;
			ctx.setLineDash([dash, dash]);
			ctx.moveTo(p1.x * hpr, p1.y * vpr);
			ctx.lineTo(p2.x * hpr, p2.y * vpr);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		// 2. Horizontal Fibonacci level lines & text labels
		const xMin = Math.min(p1.x, p2.x);
		const xMax = Math.max(p1.x, p2.x);
		const xStart = extendLines ? 0 : xMin;
		const xEnd = extendLines ? width : xMax - xMin < 30 ? xMin + 50 : xMax;

		this._drawLevelLines(ctx, levels, xStart, xEnd, hpr, vpr);

		// 3. Anchor handles
		this._drawAnchorHandle(ctx, p1, hpr, vpr);
		this._drawAnchorHandle(ctx, p2, hpr, vpr);
	}

	private _drawExtension(
		ctx: CanvasRenderingContext2D,
		data: ExtensionRenderData,
		hpr: number,
		vpr: number,
		width: number
	): void {
		const { p1, p2, p3, levels, extendLines } = data;

		// 1. Trendlines connecting p1 -> p2 -> p3
		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = DEFAULT_TRENDLINE_COLOR;
			ctx.lineWidth = DEFAULT_TRENDLINE_WIDTH * hpr;
			const dash = 3 * hpr;
			ctx.setLineDash([dash, dash]);
			ctx.moveTo(p1.x * hpr, p1.y * vpr);
			ctx.lineTo(p2.x * hpr, p2.y * vpr);
			ctx.lineTo(p3.x * hpr, p3.y * vpr);
			ctx.stroke();
		} finally {
			ctx.restore();
		}

		// 2. Horizontal Fibonacci level lines & text labels
		const xMin = Math.min(p1.x, p2.x, p3.x);
		const xMax = Math.max(p1.x, p2.x, p3.x);
		const xStart = extendLines ? 0 : xMin;
		const xEnd = extendLines ? width : xMax - xMin < 30 ? xMin + 50 : xMax;

		this._drawLevelLines(ctx, levels, xStart, xEnd, hpr, vpr);

		// 3. Anchor handles
		this._drawAnchorHandle(ctx, p1, hpr, vpr);
		this._drawAnchorHandle(ctx, p2, hpr, vpr);
		this._drawAnchorHandle(ctx, p3, hpr, vpr);
	}

	private _drawLevelLines(
		ctx: CanvasRenderingContext2D,
		levels: ProjectedFibLevel[],
		xStart: number,
		xEnd: number,
		hpr: number,
		vpr: number
	): void {
		const fontSize = Math.max(9, Math.round(11 * vpr));

		for (const level of levels) {
			if (level.enabled === false) continue;
			const color = level.color || DEFAULT_TRENDLINE_COLOR;
			const ly = level.y * vpr;

			// Level line
			ctx.save();
			try {
				ctx.beginPath();
				ctx.strokeStyle = color;
				ctx.lineWidth = DEFAULT_LEVEL_LINE_WIDTH * hpr;
				ctx.setLineDash(DEFAULT_LEVEL_LINE_DASH.map((d) => d * hpr));
				ctx.moveTo(xStart * hpr, ly);
				ctx.lineTo(xEnd * hpr, ly);
				ctx.stroke();
			} finally {
				ctx.restore();
			}

			// Label
			if (level.label) {
				ctx.save();
				try {
					ctx.font = `bold ${fontSize}px sans-serif`;
					ctx.fillStyle = color;
					ctx.textAlign = 'left';
					ctx.textBaseline = 'bottom';
					ctx.fillText(level.label, (xStart + 4) * hpr, ly - 2 * vpr);
				} finally {
					ctx.restore();
				}
			}
		}
	}

	private _drawAnchorHandle(
		ctx: CanvasRenderingContext2D,
		point: ProjectedFibPoint,
		hpr: number,
		vpr: number
	): void {
		const px = point.x * hpr;
		const py = point.y * vpr;
		const radius = HANDLE_RADIUS * hpr;

		// Highlight ring on hover, drag, or selection
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

		// Node circle
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

	private _drawDrawingPreview(
		ctx: CanvasRenderingContext2D,
		preview: FibDrawingPreviewData,
		hpr: number,
		vpr: number
	): void {
		const mouse = preview.currentMouse;
		if (!mouse) return;

		const mouseX = mouse.x * hpr;
		const mouseY = mouse.y * vpr;

		// 1. Dashed trendline connecting placed points and connecting last point to mouse
		if (preview.placedPoints.length > 0) {
			ctx.save();
			try {
				ctx.beginPath();
				ctx.strokeStyle = DEFAULT_TRENDLINE_COLOR;
				ctx.lineWidth = DEFAULT_TRENDLINE_WIDTH * hpr;
				const dash = PREVIEW_LINE_DASH[0] * hpr;
				ctx.setLineDash([dash, dash]);

				const first = preview.placedPoints[0];
				ctx.moveTo(first.x * hpr, first.y * vpr);

				for (let i = 1; i < preview.placedPoints.length; i++) {
					const pt = preview.placedPoints[i];
					ctx.lineTo(pt.x * hpr, pt.y * vpr);
				}

				ctx.lineTo(mouseX, mouseY);
				ctx.stroke();
			} finally {
				ctx.restore();
			}

			// Draw handles for already placed points in drawing preview
			for (const pt of preview.placedPoints) {
				this._drawAnchorHandle(ctx, pt, hpr, vpr);
			}
		}

		// 2. Ghost preview level lines
		if (preview.previewLevels && preview.previewLevels.length > 0) {
			ctx.save();
			try {
				ctx.globalAlpha = PREVIEW_ALPHA;
				const allX = preview.placedPoints.map((p) => p.x).concat(mouse.x);
				const xMin = Math.min(...allX);
				const xMax = Math.max(...allX);
				const xStart = xMin;
				const xEnd = xMax - xMin < 30 ? xMin + 50 : xMax;
				this._drawLevelLines(ctx, preview.previewLevels, xStart, xEnd, hpr, vpr);
			} finally {
				ctx.restore();
			}
		}

		// 3. Ghost anchor handle at mouse position
		ctx.save();
		try {
			ctx.globalAlpha = PREVIEW_ALPHA;
			const radius = HANDLE_RADIUS * hpr;

			ctx.beginPath();
			ctx.arc(mouseX, mouseY, radius, 0, Math.PI * 2);
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
