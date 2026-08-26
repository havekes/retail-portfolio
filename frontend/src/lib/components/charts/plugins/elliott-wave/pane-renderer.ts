import type { BitmapCoordinatesRenderingScope, CanvasRenderingTarget2D } from 'fancy-canvas';
import type { IPrimitivePaneRenderer, Time } from 'lightweight-charts';
import type { WaveDegree, WavePointId, WaveType } from '$lib/utils/finance/elliott-wave';
import { type DegreeVisualConfig, PREVIEW_ALPHA } from './constants';

export interface ProjectedWavePoint {
	wave: WavePointId;
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
	type?: WaveType;
	config: DegreeVisualConfig;
	points: ProjectedWavePoint[];
	isActiveDegree: boolean;
	isSelected?: boolean;
}

export interface DrawingPreviewData {
	degree: WaveDegree;
	type?: WaveType;
	config: DegreeVisualConfig;
	nextWave: WavePointId;
	lastPoint: ProjectedWavePoint | null;
	currentMouse: { x: number; y: number } | null;
}

export interface ElliottWaveRendererData {
	degrees: DegreeRenderData[];
	preview: DrawingPreviewData | null;
}

export const IMPULSE_COLOR = '#22c55e';
export const CORRECTIVE_COLOR = '#ef4444';
export const VERTICAL_LABEL_OFFSET = 14;

export function getWaveColor(waveOrType: WavePointId | WaveType, maybeWave?: WavePointId): string {
	if (
		waveOrType === 'corrective' ||
		waveOrType === 'A' ||
		waveOrType === 'B' ||
		waveOrType === 'C' ||
		maybeWave === 'A' ||
		maybeWave === 'B' ||
		maybeWave === 'C'
	) {
		return CORRECTIVE_COLOR;
	}
	return IMPULSE_COLOR;
}

export function getWaveLabelOffset(wave: WavePointId): number {
	// Top offset (above the point, -14px) for peaks: waves 1, 3, 5 (and corrective wave B)
	if (wave === 1 || wave === 3 || wave === 5 || wave === 'B') {
		return -VERTICAL_LABEL_OFFSET;
	}
	// Bottom offset (below the point, +14px) for troughs: waves 2, 4 (and corrective waves A, C)
	if (wave === 2 || wave === 4 || wave === 'A' || wave === 'C') {
		return VERTICAL_LABEL_OFFSET;
	}
	return 0;
}

export function getWaveOrder(wave: WavePointId): number {
	switch (wave) {
		case 0:
			return 0;
		case 1:
		case 'A':
			return 1;
		case 2:
		case 'B':
			return 2;
		case 3:
		case 'C':
			return 3;
		case 4:
			return 4;
		case 5:
			return 5;
		default:
			return 0;
	}
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

		const sortedPoints = [...degreeData.points].sort(
			(a, b) => getWaveOrder(a.wave) - getWaveOrder(b.wave)
		);
		for (let i = 1; i < sortedPoints.length; i++) {
			const prev = sortedPoints[i - 1];
			const curr = sortedPoints[i];

			if (getWaveOrder(curr.wave) === getWaveOrder(prev.wave) + 1) {
				const x1 = prev.x * hpr;
				const y1 = prev.y * vpr;
				const x2 = curr.x * hpr;
				const y2 = curr.y * vpr;
				const isCorrective =
					degreeData.type === 'corrective' ||
					curr.wave === 'A' ||
					curr.wave === 'B' ||
					curr.wave === 'C' ||
					prev.wave === 'A' ||
					prev.wave === 'B' ||
					prev.wave === 'C';
				const color = isCorrective ? CORRECTIVE_COLOR : IMPULSE_COLOR;

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
				// Offset wave label without background badge
				ctx.save();
				try {
					const label = degreeData.config.formatLabel(point.wave, degreeData.type);
					const fontSize = Math.max(10, Math.round(13 * vpr));
					ctx.font = `bold ${fontSize}px sans-serif`;
					const isCorrective =
						degreeData.type === 'corrective' ||
						point.wave === 'A' ||
						point.wave === 'B' ||
						point.wave === 'C';
					ctx.fillStyle = isCorrective ? CORRECTIVE_COLOR : IMPULSE_COLOR;
					ctx.textAlign = 'center';
					ctx.textBaseline = 'middle';
					const offsetY = getWaveLabelOffset(point.wave) * vpr;
					ctx.fillText(label, px, py + offsetY);
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
		const isCorrective =
			preview.type === 'corrective' ||
			preview.nextWave === 'A' ||
			preview.nextWave === 'B' ||
			preview.nextWave === 'C';
		const previewColor = isCorrective ? CORRECTIVE_COLOR : IMPULSE_COLOR;

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
				const label = preview.config.formatLabel(preview.nextWave, preview.type);
				const fontSize = Math.max(10, Math.round(13 * vpr));
				ctx.font = `bold ${fontSize}px sans-serif`;
				ctx.fillStyle = previewColor;
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				const offsetY = getWaveLabelOffset(preview.nextWave) * vpr;
				ctx.fillText(label, mouseX, mouseY + offsetY);
			} finally {
				ctx.restore();
			}
		}
	}
}
