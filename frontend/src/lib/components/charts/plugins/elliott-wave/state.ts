import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import type { DegreeWaveCount, WaveDegree, WavePoint } from '$lib/utils/finance/elliott-wave';
import { MAX_WAVE_POINTS } from './constants';

export interface PointTarget {
	degree: WaveDegree;
	wave: 0 | 1 | 2 | 3 | 4 | 5;
}

export class ElliottWaveState {
	private _activeDegree: WaveDegree = 'cycle';
	private _waveCounts: Record<WaveDegree, DegreeWaveCount | null> = {
		cycle: null,
		primary: null,
		intermediate: null
	};
	private _isDrawingMode: boolean = false;
	private _selectedDegree: WaveDegree | null = null;
	private _hoveredPoint: PointTarget | null = null;
	private _draggingPoint: PointTarget | null = null;

	private _wavePointsChanged: Delegate<{ degree: WaveDegree; waveCount: DegreeWaveCount | null }> =
		new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _degreeChanged: Delegate<WaveDegree> = new Delegate();
	private _selectionChanged: Delegate<WaveDegree | null> = new Delegate();
	private _hoverChanged: Delegate<PointTarget | null> = new Delegate();
	private _dragChanged: Delegate<PointTarget | null> = new Delegate();

	public wavePointsChanged(): ISubscription<{
		degree: WaveDegree;
		waveCount: DegreeWaveCount | null;
	}> {
		return this._wavePointsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public degreeChanged(): ISubscription<WaveDegree> {
		return this._degreeChanged;
	}

	public selectionChanged(): ISubscription<WaveDegree | null> {
		return this._selectionChanged;
	}

	public hoverChanged(): ISubscription<PointTarget | null> {
		return this._hoverChanged;
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
			this._degreeChanged.fire(degree);
		}
	}

	public getSelectedDegree(): WaveDegree | null {
		return this._selectedDegree;
	}

	public setSelectedDegree(degree: WaveDegree | null): void {
		if (this._selectedDegree !== degree) {
			this._selectedDegree = degree;
			this._selectionChanged.fire(degree);
		}
	}

	public isDrawingMode(): boolean {
		return this._isDrawingMode;
	}

	public setDrawingMode(enabled: boolean): void {
		if (this._isDrawingMode !== enabled) {
			this._isDrawingMode = enabled;
			if (enabled && this._selectedDegree !== null) {
				this.setSelectedDegree(null);
			}
			this._drawingModeChanged.fire(enabled);
		}
	}

	public getWaveCount(degree?: WaveDegree): DegreeWaveCount | null {
		const targetDegree = degree ?? this._activeDegree;
		return this._waveCounts[targetDegree] ?? null;
	}

	public setWaveCount(degree: WaveDegree, waveCount: DegreeWaveCount | null): void {
		if (!waveCount && this._selectedDegree === degree) {
			this.setSelectedDegree(null);
		}
		this._waveCounts[degree] = waveCount
			? {
					...waveCount,
					points: [...(waveCount.points || [])]
				}
			: null;
		this._wavePointsChanged.fire({ degree, waveCount: this._waveCounts[degree] });
	}

	public getAllWaveCounts(): Record<WaveDegree, DegreeWaveCount | null> {
		return {
			cycle: this._waveCounts.cycle
				? { ...this._waveCounts.cycle, points: [...this._waveCounts.cycle.points] }
				: null,
			primary: this._waveCounts.primary
				? { ...this._waveCounts.primary, points: [...this._waveCounts.primary.points] }
				: null,
			intermediate: this._waveCounts.intermediate
				? { ...this._waveCounts.intermediate, points: [...this._waveCounts.intermediate.points] }
				: null
		};
	}

	public setAllWaveCounts(waves: Partial<Record<WaveDegree, DegreeWaveCount | null>>): void {
		this.setWaveCount('cycle', waves.cycle ?? null);
		this.setWaveCount('primary', waves.primary ?? null);
		this.setWaveCount('intermediate', waves.intermediate ?? null);
	}

	public getPoints(degree?: WaveDegree): WavePoint[] {
		return this.getWaveCount(degree)?.points ?? [];
	}

	public addPoint(point: { time: Time; price: number }, degree?: WaveDegree): WavePoint {
		const targetDegree = degree ?? this._activeDegree;
		const existingPoints = [...this.getPoints(targetDegree)];

		const isResetting = existingPoints.length >= MAX_WAVE_POINTS;
		if (isResetting) {
			existingPoints.length = 0;
		}

		const nextWave = existingPoints.length as 0 | 1 | 2 | 3 | 4 | 5;
		const newPoint: WavePoint = {
			wave: nextWave,
			time: point.time,
			price: point.price
		};

		existingPoints.push(newPoint);

		const currentCount = isResetting ? null : this._waveCounts[targetDegree];
		const updatedCount: DegreeWaveCount = {
			points: existingPoints,
			wave3Target: currentCount?.wave3Target ?? (nextWave === 3 ? point.price : null),
			wave5Target: currentCount?.wave5Target ?? (nextWave === 5 ? point.price : null)
		};

		this._waveCounts[targetDegree] = updatedCount;
		this._wavePointsChanged.fire({ degree: targetDegree, waveCount: updatedCount });

		if (existingPoints.length >= MAX_WAVE_POINTS) {
			this.setDrawingMode(false);
		}

		return newPoint;
	}

	public updatePoint(
		wave: 0 | 1 | 2 | 3 | 4 | 5,
		update: { time?: Time; price?: number },
		degree?: WaveDegree
	): boolean {
		const targetDegree = degree ?? this._activeDegree;
		const currentCount = this._waveCounts[targetDegree];
		if (!currentCount || !currentCount.points) return false;

		const pointIndex = currentCount.points.findIndex((p) => p.wave === wave);
		if (pointIndex === -1) return false;

		const points = [...currentCount.points];
		const targetPoint = { ...points[pointIndex] };

		if (update.time !== undefined) {
			targetPoint.time = update.time;
		}
		if (update.price !== undefined) {
			targetPoint.price = update.price;
		}

		points[pointIndex] = targetPoint;

		const updatedCount: DegreeWaveCount = {
			...currentCount,
			points,
			wave3Target:
				wave === 3 && update.price !== undefined ? update.price : currentCount.wave3Target,
			wave5Target:
				wave === 5 && update.price !== undefined ? update.price : currentCount.wave5Target
		};

		this._waveCounts[targetDegree] = updatedCount;
		this._wavePointsChanged.fire({ degree: targetDegree, waveCount: updatedCount });
		return true;
	}

	public clearWave(degree?: WaveDegree): void {
		const targetDegree = degree ?? this._activeDegree;
		if (this._selectedDegree === targetDegree) {
			this.setSelectedDegree(null);
		}
		this._waveCounts[targetDegree] = null;
		this._wavePointsChanged.fire({ degree: targetDegree, waveCount: null });
	}

	public setHoveredPoint(point: PointTarget | null): void {
		const changed =
			this._hoveredPoint?.degree !== point?.degree || this._hoveredPoint?.wave !== point?.wave;
		if (changed) {
			this._hoveredPoint = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): PointTarget | null {
		return this._hoveredPoint;
	}

	public setDraggingPoint(point: PointTarget | null): void {
		const changed =
			this._draggingPoint?.degree !== point?.degree || this._draggingPoint?.wave !== point?.wave;
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
		this._selectionChanged.destroy();
		this._hoverChanged.destroy();
		this._dragChanged.destroy();
	}
}
