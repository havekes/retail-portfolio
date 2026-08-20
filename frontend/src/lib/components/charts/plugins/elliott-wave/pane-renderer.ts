import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import type { WaveDegree } from '$lib/utils/finance/elliott-wave';
import { type DegreeVisualConfig, PREVIEW_ALPHA } from './constants';

export interface ProjectedWavePoint {
	wave: 0 | 1 | 2 | 3 | 4 | 5;
	x: number;
	y: number;
	time: Time;
	price: number;
	isHovered?: boolean;
	isDragging?: boolean;
}

export interface DegreeRenderData {
	degree: WaveDegree;
	config: DegreeVisualConfig;
	points: ProjectedWavePoint[];
	isActiveDegree: boolean;
}

export interface DrawingPreviewData {
	degree: WaveDegree;
	config: DegreeVisualConfig;
	nextWave: 0 | 1 | 2 | 3 | 4 | 5;
	lastPoint: ProjectedWavePoint | null;
	currentMouse: { x: number; y: number } | null;
}

export interface ElliottWaveRendererData {
	degrees: DegreeRenderData[];
	preview: DrawingPreviewData | null;
}

export class ElliottWavePaneRenderer implements IPrimitivePaneRenderer {
	private _data: ElliottWaveRendererData | null = null;

	public update(data: ElliottWaveRendererData | null): void {
		this._data = data;
	}

	public draw(target: CanvasRenderingTarget2D): void {
		target.useBitmapCoordinateSpace((scope: BitmapCoordinatesRenderingScope) => {
			if (!this._data) return;
			const ctx = scope.context;
			const hpr = scope.horizontalPixelRatio;
			const vpr = scope.verticalPixelRatio;

			// 1. Draw connecting lines for each degree
			for (const degreeData of this._data.degrees) {
				this._drawConnectingLines(ctx, degreeData, hpr, vpr);
			}

			// 2. Draw drawing preview (dashed line to mouse and ghost badge)
			if (this._data.preview && this._data.preview.currentMouse) {
				this._drawDrawingPreview(ctx, this._data.preview, hpr, vpr);
			}

			// 3. Draw numbered wave node badges for each degree
			for (const degreeData of this._data.degrees) {
				this._drawWaveBadges(ctx, degreeData, hpr, vpr);
			}
		});
	}

	private _drawConnectingLines(
		ctx: CanvasRenderingContext2D,
		degreeData: DegreeRenderData,
		hpr: number,
		vpr: number
	): void {
		if (degreeData.points.length < 2) return;

		const sortedPoints = [...degreeData.points].sort((a, b) => a.wave - b.wave);

		ctx.save();
		try {
			ctx.beginPath();
			ctx.strokeStyle = degreeData.config.color;
			ctx.lineWidth = degreeData.config.lineWidth * hpr;
			ctx.lineCap = 'round';
			ctx.lineJoin = 'round';

			ctx.moveTo(sortedPoints[0].x * hpr, sortedPoints[0].y * vpr);
			for (let i = 1; i < sortedPoints.length; i++) {
				ctx.lineTo(sortedPoints[i].x * hpr, sortedPoints[i].y * vpr);
			}
			ctx.stroke();
		} finally {
			ctx.restore();
		}
	}

	private _drawWaveBadges(
		ctx: CanvasRenderingContext2D,
		degreeData: DegreeRenderData,
		hpr: number,
		vpr: number
	): void {
		for (const point of degreeData.points) {
			const px = point.x * hpr;
			const py = point.y * vpr;
			const radius = degreeData.config.nodeRadius * hpr;

			// Highlight ring on hover or drag
			if (point.isHovered || point.isDragging) {
				ctx.save();
				try {
					ctx.beginPath();
					ctx.arc(px, py, radius + 4 * hpr, 0, Math.PI * 2);
					ctx.fillStyle = degreeData.config.hoverRingColor;
					ctx.fill();
					ctx.lineWidth = 1.5 * hpr;
					ctx.strokeStyle = degreeData.config.color;
					ctx.stroke();
				} finally {
					ctx.restore();
				}
			}

			// Node badge circle
			ctx.save();
			try {
				ctx.beginPath();
				ctx.arc(px, py, radius, 0, Math.PI * 2);
				ctx.fillStyle = degreeData.config.badgeBgColor;
				ctx.fill();
				ctx.lineWidth = 2 * hpr;
				ctx.strokeStyle = degreeData.config.badgeBorderColor;
				ctx.stroke();

				// Centered wave label (omit text for wave 0 anchor point)
				if (point.wave !== 0) {
					const label = degreeData.config.formatLabel(point.wave);
					const fontSize = Math.max(9, Math.round(11 * vpr));
					ctx.font = `bold ${fontSize}px sans-serif`;
					ctx.fillStyle = degreeData.config.badgeTextColor;
					ctx.textAlign = 'center';
					ctx.textBaseline = 'middle';
					ctx.fillText(label, px, py);
				}
			} finally {
				ctx.restore();
			}
		}
	}

	private _drawDrawingPreview(
		ctx: CanvasRenderingContext2D,
		preview: DrawingPreviewData,
		hpr: number,
		vpr: number
	): void {
		const mouse = preview.currentMouse;
		if (!mouse) return;

		const mouseX = mouse.x * hpr;
		const mouseY = mouse.y * vpr;

		// Dashed line from last placed point to current mouse position
		if (preview.lastPoint) {
			const lastX = preview.lastPoint.x * hpr;
			const lastY = preview.lastPoint.y * vpr;

			ctx.save();
			try {
				ctx.beginPath();
				ctx.strokeStyle = preview.config.color;
				ctx.lineWidth = preview.config.lineWidth * hpr;
				const dash = 4 * hpr;
				ctx.setLineDash([dash, dash]);
				ctx.moveTo(lastX, lastY);
				ctx.lineTo(mouseX, mouseY);
				ctx.stroke();
			} finally {
				ctx.restore();
			}
		}

		// Ghost preview badge at cursor position
		ctx.save();
		try {
			ctx.globalAlpha = PREVIEW_ALPHA;
			const radius = preview.config.nodeRadius * hpr;

			ctx.beginPath();
			ctx.arc(mouseX, mouseY, radius, 0, Math.PI * 2);
			ctx.fillStyle = preview.config.badgeBgColor;
			ctx.fill();
			ctx.lineWidth = 2 * hpr;
			ctx.strokeStyle = preview.config.badgeBorderColor;
			ctx.stroke();

			if (preview.nextWave !== 0) {
				const label = preview.config.formatLabel(preview.nextWave);
				const fontSize = Math.max(9, Math.round(11 * vpr));
				ctx.font = `bold ${fontSize}px sans-serif`;
				ctx.fillStyle = preview.config.badgeTextColor;
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				ctx.fillText(label, mouseX, mouseY);
			}
		} finally {
			ctx.restore();
		}
	}
}
