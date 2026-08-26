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
	isSelected?: boolean;
}

export interface DegreeRenderData {
	degree: WaveDegree;
	config: DegreeVisualConfig;
	points: ProjectedWavePoint[];
	isActiveDegree: boolean;
	isSelected?: boolean;
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

export const IMPULSE_COLOR = '#22c55e';
export const CORRECTIVE_COLOR = '#ef4444';

export function getWaveColor(wave: number): string {
	if (wave === 1 || wave === 3 || wave === 5) {
		return IMPULSE_COLOR;
	}
	if (wave === 2 || wave === 4) {
		return CORRECTIVE_COLOR;
	}
	return IMPULSE_COLOR;
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

			// 1. Draw wave segments connecting points
			for (const degreeData of this._data.degrees) {
				this._drawWaveSegments(ctx, degreeData, hpr, vpr);
			}

			// 2. Draw drawing preview (dashed guide line to mouse and ghost label)
			if (this._data.preview && this._data.preview.currentMouse) {
				this._drawDrawingPreview(ctx, this._data.preview, hpr, vpr);
			}

			// 3. Draw wave labels / nodes for each degree
			for (const degreeData of this._data.degrees) {
				this._drawWaveBadges(ctx, degreeData, hpr, vpr);
			}
		});
	}

	private _drawWaveSegments(
		ctx: CanvasRenderingContext2D,
		degreeData: DegreeRenderData,
		hpr: number,
		vpr: number
	): void {
		if (degreeData.points.length < 2) return;

		const sortedPoints = [...degreeData.points].sort((a, b) => a.wave - b.wave);
		for (let i = 1; i < sortedPoints.length; i++) {
			const prev = sortedPoints[i - 1];
			const curr = sortedPoints[i];

			if (curr.wave === prev.wave + 1) {
				const x1 = prev.x * hpr;
				const y1 = prev.y * vpr;
				const x2 = curr.x * hpr;
				const y2 = curr.y * vpr;
				const color = getWaveColor(curr.wave);

				ctx.save();
				try {
					ctx.beginPath();
					ctx.strokeStyle = color;
					ctx.lineWidth = degreeData.config.lineWidth * hpr;
					ctx.moveTo(x1, y1);
					ctx.lineTo(x2, y2);
					ctx.stroke();
				} finally {
					ctx.restore();
				}
			}
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

			// Highlight ring on hover, drag, or selection
			if (point.isHovered || point.isDragging || degreeData.isSelected || point.isSelected) {
				const ringColor =
					point.isHovered || point.isDragging
						? degreeData.config.hoverRingColor
						: (degreeData.config.selectedRingColor ?? degreeData.config.hoverRingColor);
				ctx.save();
				try {
					ctx.beginPath();
					ctx.arc(px, py, radius + 4 * hpr, 0, Math.PI * 2);
					ctx.fillStyle = ringColor;
					ctx.fill();
					ctx.lineWidth = 1.5 * hpr;
					ctx.strokeStyle = degreeData.config.color;
					ctx.stroke();
				} finally {
					ctx.restore();
				}
			}

			// Point 0: anchor point dot
			if (point.wave === 0) {
				ctx.save();
				try {
					ctx.beginPath();
					ctx.arc(px, py, 3 * hpr, 0, Math.PI * 2);
					ctx.fillStyle = degreeData.config.color;
					ctx.fill();
				} finally {
					ctx.restore();
				}
			} else {
				// Centered wave label without background badge
				ctx.save();
				try {
					const label = degreeData.config.formatLabel(point.wave);
					const fontSize = Math.max(10, Math.round(13 * vpr));
					ctx.font = `bold ${fontSize}px sans-serif`;
					ctx.fillStyle = getWaveColor(point.wave);
					ctx.textAlign = 'center';
					ctx.textBaseline = 'middle';
					ctx.fillText(label, px, py);
				} finally {
					ctx.restore();
				}
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
		const previewColor = getWaveColor(preview.nextWave);

		// Dashed line from last placed point to current mouse position
		if (preview.lastPoint) {
			const lastX = preview.lastPoint.x * hpr;
			const lastY = preview.lastPoint.y * vpr;

			ctx.save();
			try {
				ctx.beginPath();
				ctx.strokeStyle = previewColor;
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

		// Ghost preview label at cursor position (without badge background)
		if (preview.nextWave === 0) {
			ctx.save();
			try {
				ctx.globalAlpha = PREVIEW_ALPHA;
				ctx.beginPath();
				ctx.arc(mouseX, mouseY, 3 * hpr, 0, Math.PI * 2);
				ctx.fillStyle = preview.config.color;
				ctx.fill();
			} finally {
				ctx.restore();
			}
		} else {
			ctx.save();
			try {
				ctx.globalAlpha = PREVIEW_ALPHA;
				const label = preview.config.formatLabel(preview.nextWave);
				const fontSize = Math.max(10, Math.round(13 * vpr));
				ctx.font = `bold ${fontSize}px sans-serif`;
				ctx.fillStyle = previewColor;
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				ctx.fillText(label, mouseX, mouseY);
			} finally {
				ctx.restore();
			}
		}
	}
}
