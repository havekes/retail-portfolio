import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import {
	normalizeWaveIds,
	selectDegreeWave,
	type DegreeWaveCount,
	type WaveDegree,
	type WavePoint,
	type WavePointId,
	type WaveType
} from '$lib/utils/finance/elliott-wave';
import { MAX_CORRECTIVE_POINTS, MAX_IMPULSE_POINTS } from './constants';
import { generateUUID } from '$lib/utils/finance/rewind';
import { normalizeDrawingTime } from '$lib/utils/finance/drawing-time';

export interface PointTarget {
	degree: WaveDegree;
	wave: WavePointId;
	waveId?: string;
}

export interface WavePointsChangedEvent {
	degree: WaveDegree;
	waveCount: DegreeWaveCount | null;
}

export class ElliottWaveState {
	private _activeDegree: WaveDegree = 'cycle';
	private _activeWaveType: WaveType = 'impulse';
	private _waves: DegreeWaveCount[] = [];
	private _drawingWaveId: string | null = null;
	private _selectedWaveId: string | null = null;
	private _isDrawingMode: boolean = false;
	private _selectedDegree: WaveDegree | null = null;
	private _hoveredPoint: PointTarget | null = null;
	private _hoveredLine: PointTarget | null = null;
	private _draggingPoint: PointTarget | null = null;

	private _wavePointsChanged: Delegate<WavePointsChangedEvent> = new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _degreeChanged: Delegate<WaveDegree> = new Delegate();
	private _waveTypeChanged: Delegate<WaveType> = new Delegate();
	private _selectionChanged: Delegate<WaveDegree | null> = new Delegate();
	private _selectedWaveChanged: Delegate<string | null> = new Delegate();
	private _hoverChanged: Delegate<PointTarget | null> = new Delegate();
	private _hoveredLineChanged: Delegate<PointTarget | null> = new Delegate();
	private _dragChanged: Delegate<PointTarget | null> = new Delegate();

	public wavePointsChanged(): ISubscription<WavePointsChangedEvent> {
		return this._wavePointsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public degreeChanged(): ISubscription<WaveDegree> {
		return this._degreeChanged;
	}

	public waveTypeChanged(): ISubscription<WaveType> {
		return this._waveTypeChanged;
	}

	public selectionChanged(): ISubscription<WaveDegree | null> {
		return this._selectionChanged;
	}

	public selectedWaveChanged(): ISubscription<string | null> {
		return this._selectedWaveChanged;
	}

	public hoverChanged(): ISubscription<PointTarget | null> {
		return this._hoverChanged;
	}

	public hoveredLineChanged(): ISubscription<PointTarget | null> {
		return this._hoveredLineChanged;
	}

	public dragChanged(): ISubscription<PointTarget | null> {
		return this._dragChanged;
	}

	public getActiveDegree(): WaveDegree {
		return this._activeDegree;
	}

	public setActiveDegree(degree: WaveDegree): void {
		if (this._activeDegree !== degree) {
			this._activeDegree = degree;
			this._drawingWaveId = null;
			this._degreeChanged.fire(degree);
		}
	}

	public getActiveWaveType(): WaveType {
		return this._activeWaveType;
	}

	public setActiveWaveType(type: WaveType): void {
		if (this._activeWaveType !== type) {
			this._activeWaveType = type;
			this._drawingWaveId = null;
			this._waveTypeChanged.fire(type);
		}
	}

	public getSelectedDegree(): WaveDegree | null {
		return this._selectedDegree;
	}

	public setSelectedDegree(degree: WaveDegree | null): void {
		if (this._selectedDegree !== degree) {
			this._selectedDegree = degree;
			if (degree === null) {
				this._selectedWaveId = null;
				this._selectedWaveChanged.fire(null);
			} else if (this._selectedWaveId) {
				const current = this._waves.find((w) => w.id === this._selectedWaveId);
				if (current && current.degree !== degree) {
					this._selectedWaveId = null;
					this._selectedWaveChanged.fire(null);
				}
			}
			this._selectionChanged.fire(degree);
		}
	}

	public getSelectedWaveId(): string | null {
		return this._selectedWaveId;
	}

	public setSelectedWaveId(waveId: string | null): void {
		if (this._selectedWaveId !== waveId) {
			this._selectedWaveId = waveId;
			if (waveId) {
				const wave = this._waves.find((w) => w.id === waveId);
				if (wave && wave.degree) {
					this.setSelectedDegree(wave.degree);
				}
			}
			this._selectedWaveChanged.fire(waveId);
		}
	}

	public isDrawingMode(): boolean {
		return this._isDrawingMode;
	}

	public setDrawingMode(enabled: boolean): void {
		if (this._isDrawingMode !== enabled) {
			this._isDrawingMode = enabled;
			if (enabled) {
				if (this._selectedDegree !== null || this._selectedWaveId !== null) {
					this.setSelectedDegree(null);
					this.setSelectedWaveId(null);
				}
				this._drawingWaveId = generateUUID();
			} else {
				if (this._drawingWaveId) {
					const drawingIdx = this._waves.findIndex((w) => w.id === this._drawingWaveId);
					if (drawingIdx !== -1) {
						const wave = this._waves[drawingIdx];
						const maxPts = wave.type === 'corrective' ? MAX_CORRECTIVE_POINTS : MAX_IMPULSE_POINTS;
						if (wave.points.length < maxPts) {
							this._waves.splice(drawingIdx, 1);
							this._wavePointsChanged.fire({
								degree: wave.degree,
								waveCount: null
							});
						}
					}
					this._drawingWaveId = null;
				}
			}
			this._drawingModeChanged.fire(enabled);
		}
	}

	public cancelDrawing(): void {
		if (!this._isDrawingMode) return;
		if (this._drawingWaveId) {
			const drawingIdx = this._waves.findIndex((w) => w.id === this._drawingWaveId);
			if (drawingIdx !== -1) {
				const wave = this._waves[drawingIdx];
				const maxPts = wave.type === 'corrective' ? MAX_CORRECTIVE_POINTS : MAX_IMPULSE_POINTS;
				if (wave.points.length < maxPts) {
					this._waves.splice(drawingIdx, 1);
					this._wavePointsChanged.fire({
						degree: wave.degree,
						waveCount: null
					});
				}
			}
			this._drawingWaveId = null;
		}
		this.setDrawingMode(false);
	}

	public getDrawingWave(): DegreeWaveCount | null {
		if (!this._isDrawingMode || !this._drawingWaveId) return null;
		return this._waves.find((w) => w.id === this._drawingWaveId) ?? null;
	}

	public getWaveCount(degree?: WaveDegree): DegreeWaveCount | null {
		const targetDegree = degree ?? this._activeDegree;

		if (this._drawingWaveId) {
			const drawing = this._waves.find((w) => w.id === this._drawingWaveId);
			if (drawing && drawing.degree === targetDegree) {
				return drawing;
			}
		}

		if (this._selectedWaveId) {
			const selected = this._waves.find((w) => w.id === this._selectedWaveId);
			if (selected && selected.degree === targetDegree) {
				return selected;
			}
		}

		return selectDegreeWave(this._waves, targetDegree, {
			preferredType: this._activeWaveType,
			prefer: 'last'
		});
	}

	public getAllWaves(): DegreeWaveCount[] {
		return this._waves.map((w) => ({
			...w,
			points: [...w.points]
		}));
	}

	public getWaves(degree?: WaveDegree): DegreeWaveCount[] {
		const list = degree ? this._waves.filter((w) => w.degree === degree) : this._waves;
		return list.map((w) => ({
			...w,
			points: [...w.points]
		}));
	}

	public getWaveById(id: string): DegreeWaveCount | undefined {
		const found = this._waves.find((w) => w.id === id);
		return found ? { ...found, points: [...found.points] } : undefined;
	}

	public setWaves(waves: DegreeWaveCount[]): void {
		this._waves = normalizeWaveIds(waves);
		if (this._selectedWaveId && !this._waves.some((w) => w.id === this._selectedWaveId)) {
			this._selectedWaveId = null;
			this.setSelectedDegree(null);
		}
		this._wavePointsChanged.fire({
			degree: this._activeDegree,
			waveCount: this.getWaveCount(this._activeDegree)
		});
	}

	public getPoints(degree?: WaveDegree): WavePoint[] {
		return this.getWaveCount(degree)?.points ?? [];
	}

	public addPoint(point: { time: Time; price: number }, degree?: WaveDegree): WavePoint {
		const targetDegree = degree ?? this._activeDegree;
		const isCorrective = this._activeWaveType === 'corrective';
		const maxPoints = isCorrective ? MAX_CORRECTIVE_POINTS : MAX_IMPULSE_POINTS;

		let currentWave: DegreeWaveCount | undefined;

		if (this._drawingWaveId) {
			const drawing = this._waves.find((w) => w.id === this._drawingWaveId);
			if (drawing && drawing.degree === targetDegree && drawing.type === this._activeWaveType) {
				currentWave = drawing;
			}
		}

		if (!currentWave) {
			const waveId = generateUUID();
			this._drawingWaveId = waveId;
			currentWave = {
				id: waveId,
				degree: targetDegree,
				type: this._activeWaveType,
				points: [],
				wave3Target: null,
				wave5Target: null
			};
			this._waves.push(currentWave);
		}

		const existingPoints = currentWave.points;

		let nextWave: WavePointId;
		if (isCorrective) {
			const seq: WavePointId[] = [0, 'A', 'B', 'C'];
			nextWave = seq[existingPoints.length] ?? 0;
		} else {
			nextWave = existingPoints.length as 0 | 1 | 2 | 3 | 4 | 5;
		}

		// Canonicalize to epoch seconds on ingestion so anchors are timeframe-independent.
		const newPoint: WavePoint = {
			wave: nextWave,
			time: normalizeDrawingTime(point.time),
			price: point.price
		};

		existingPoints.push(newPoint);

		if (nextWave === 3) {
			currentWave.wave3Target = point.price;
		} else if (nextWave === 5) {
			currentWave.wave5Target = point.price;
		}

		this._wavePointsChanged.fire({
			degree: targetDegree,
			waveCount: currentWave
		});

		if (existingPoints.length >= maxPoints) {
			this._drawingWaveId = null;
			this.setDrawingMode(false);
		}

		return newPoint;
	}

	public updatePoint(
		wave: WavePointId,
		update: { time?: Time; price?: number },
		degree?: WaveDegree,
		waveId?: string
	): boolean {
		let currentWave: DegreeWaveCount | undefined;
		if (waveId) {
			currentWave = this._waves.find((w) => w.id === waveId);
		} else if (this._selectedWaveId) {
			currentWave = this._waves.find((w) => w.id === this._selectedWaveId);
		} else if (degree) {
			currentWave = this._waves.find(
				(w) => w.degree === degree && w.points.some((p) => p.wave === wave)
			);
		}

		if (!currentWave) {
			const targetDegree = degree ?? this._activeDegree;
			currentWave = this._waves.findLast(
				(w) => w.degree === targetDegree && w.points.some((p) => p.wave === wave)
			);
		}

		if (!currentWave || !currentWave.points) return false;

		const pointIndex = currentWave.points.findIndex((p) => p.wave === wave);
		if (pointIndex === -1) return false;

		const points = [...currentWave.points];
		const targetPoint = { ...points[pointIndex] };

		if (update.time !== undefined) {
			targetPoint.time = normalizeDrawingTime(update.time);
		}
		if (update.price !== undefined) {
			targetPoint.price = update.price;
		}

		points[pointIndex] = targetPoint;
		currentWave.points = points;

		if (wave === 3 && update.price !== undefined) {
			currentWave.wave3Target = update.price;
		}
		if (wave === 5 && update.price !== undefined) {
			currentWave.wave5Target = update.price;
		}

		this._wavePointsChanged.fire({
			degree: currentWave.degree,
			waveCount: currentWave
		});
		return true;
	}

	public clearWave(waveIdOrDegree?: string | WaveDegree): void {
		if (!waveIdOrDegree) {
			if (this._selectedWaveId) {
				this.removeWave(this._selectedWaveId);
				return;
			}
			const lastWave = this._waves[this._waves.length - 1];
			if (lastWave) {
				this.removeWave(lastWave.id);
			}
			return;
		}

		const waveById = this._waves.find((w) => w.id === waveIdOrDegree);
		if (waveById) {
			this.removeWave(waveById.id);
			return;
		}

		const degree = waveIdOrDegree as WaveDegree;
		if (this._selectedWaveId) {
			const selected = this._waves.find((w) => w.id === this._selectedWaveId);
			if (selected && selected.degree === degree) {
				this.removeWave(selected.id);
				return;
			}
		}

		const degreeIdx = this._waves.findLastIndex((w) => w.degree === degree);
		if (degreeIdx !== -1) {
			this.removeWave(this._waves[degreeIdx].id);
		} else if (this._selectedDegree === degree) {
			this.setSelectedDegree(null);
		}
	}

	public removeWave(id: string): boolean {
		const index = this._waves.findIndex((w) => w.id === id);
		if (index === -1) return false;
		const [removed] = this._waves.splice(index, 1);
		const clearedSelectedWave = this._selectedWaveId === id;
		if (clearedSelectedWave) {
			this._selectedWaveId = null;
		}
		if (this._drawingWaveId === id) {
			this._drawingWaveId = null;
		}
		if (this._hoveredLine?.waveId === id) {
			this.setHoveredLine(null);
		}
		if (this._hoveredPoint?.waveId === id) {
			this.setHoveredPoint(null);
		}
		if (this._draggingPoint?.waveId === id) {
			this.setDraggingPoint(null);
		}
		const degreeHasWaves = this._waves.some((w) => w.degree === removed.degree);
		if (clearedSelectedWave || (this._selectedDegree === removed.degree && !degreeHasWaves)) {
			this.setSelectedDegree(null);
		}
		if (clearedSelectedWave) {
			this._selectedWaveChanged.fire(null);
		}
		this._wavePointsChanged.fire({
			degree: removed.degree,
			waveCount: null
		});
		return true;
	}

	public setHoveredPoint(point: PointTarget | null): void {
		const changed =
			this._hoveredPoint?.degree !== point?.degree ||
			this._hoveredPoint?.wave !== point?.wave ||
			this._hoveredPoint?.waveId !== point?.waveId;
		if (changed) {
			this._hoveredPoint = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): PointTarget | null {
		return this._hoveredPoint;
	}

	public setHoveredLine(line: PointTarget | null): void {
		const changed =
			this._hoveredLine?.degree !== line?.degree ||
			this._hoveredLine?.wave !== line?.wave ||
			this._hoveredLine?.waveId !== line?.waveId;
		if (changed) {
			this._hoveredLine = line;
			this._hoveredLineChanged.fire(line);
		}
	}

	public getHoveredLine(): PointTarget | null {
		return this._hoveredLine;
	}

	public setDraggingPoint(point: PointTarget | null): void {
		const changed =
			this._draggingPoint?.degree !== point?.degree ||
			this._draggingPoint?.wave !== point?.wave ||
			this._draggingPoint?.waveId !== point?.waveId;
		if (changed) {
			this._draggingPoint = point;
			this._dragChanged.fire(point);
		}
	}

	public getDraggingPoint(): PointTarget | null {
		return this._draggingPoint;
	}

	public destroy(): void {
		this._wavePointsChanged.destroy();
		this._drawingModeChanged.destroy();
		this._degreeChanged.destroy();
		this._waveTypeChanged.destroy();
		this._selectionChanged.destroy();
		this._selectedWaveChanged.destroy();
		this._hoverChanged.destroy();
		this._hoveredLineChanged.destroy();
		this._dragChanged.destroy();
	}
}
