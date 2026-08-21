import type { Time } from 'lightweight-charts';
import { Delegate, type ISubscription } from '../helpers/delegate';
import type {
	FibExtensionDrawing,
	FibPoint,
	FibRetracementDrawing,
	FibToolType,
	SecurityFibonacciTools
} from '$lib/utils/finance/fibonacci';

export interface FibPointTarget {
	tool: FibToolType;
	pointIndex: 0 | 1 | 2;
}

export class FibonacciToolState {
	private _activeTool: FibToolType | null = 'retracement';
	private _isDrawingMode: boolean = false;
	private _retracement: FibRetracementDrawing | null = null;
	private _extension: FibExtensionDrawing | null = null;
	private _pendingPoints: FibPoint[] = [];

	private _hoveredPoint: FibPointTarget | null = null;
	private _draggingPoint: FibPointTarget | null = null;

	private _drawingsChanged: Delegate<SecurityFibonacciTools> = new Delegate();
	private _drawingModeChanged: Delegate<boolean> = new Delegate();
	private _toolChanged: Delegate<FibToolType | null> = new Delegate();
	private _hoverChanged: Delegate<FibPointTarget | null> = new Delegate();
	private _dragChanged: Delegate<FibPointTarget | null> = new Delegate();

	public drawingsChanged(): ISubscription<SecurityFibonacciTools> {
		return this._drawingsChanged;
	}

	public drawingModeChanged(): ISubscription<boolean> {
		return this._drawingModeChanged;
	}

	public toolChanged(): ISubscription<FibToolType | null> {
		return this._toolChanged;
	}

	public hoverChanged(): ISubscription<FibPointTarget | null> {
		return this._hoverChanged;
	}

	public dragChanged(): ISubscription<FibPointTarget | null> {
		return this._dragChanged;
	}

	public getActiveTool(): FibToolType | null {
		return this._activeTool;
	}

	public setActiveTool(tool: FibToolType | null): void {
		if (this._activeTool !== tool) {
			this._activeTool = tool;
			this._pendingPoints = [];
			this._toolChanged.fire(tool);
		}
	}

	public isDrawingMode(): boolean {
		return this._isDrawingMode;
	}

	public setDrawingMode(enabled: boolean): void {
		if (this._isDrawingMode !== enabled) {
			this._isDrawingMode = enabled;
			if (!enabled) {
				this._pendingPoints = [];
			}
			this._drawingModeChanged.fire(enabled);
		}
	}

	public getRetracement(): FibRetracementDrawing | null {
		return this._retracement ? { ...this._retracement } : null;
	}

	public setRetracement(drawing: FibRetracementDrawing | null): void {
		this._retracement = drawing ? { ...drawing } : null;
		this._drawingsChanged.fire(this.getDrawings());
	}

	public getExtension(): FibExtensionDrawing | null {
		return this._extension ? { ...this._extension } : null;
	}

	public setExtension(drawing: FibExtensionDrawing | null): void {
		this._extension = drawing ? { ...drawing } : null;
		this._drawingsChanged.fire(this.getDrawings());
	}

	public getDrawings(): SecurityFibonacciTools {
		return {
			retracement: this._retracement ? { ...this._retracement } : null,
			extension: this._extension ? { ...this._extension } : null
		};
	}

	public setDrawings(tools: SecurityFibonacciTools): void {
		this._retracement = tools.retracement ? { ...tools.retracement } : null;
		this._extension = tools.extension ? { ...tools.extension } : null;
		this._drawingsChanged.fire(this.getDrawings());
	}

	public getPendingPoints(): FibPoint[] {
		return [...this._pendingPoints];
	}

	public addPoint(point: FibPoint, tool?: FibToolType): FibPoint {
		const targetTool = tool ?? this._activeTool ?? 'retracement';
		if (this._activeTool !== targetTool) {
			this._activeTool = targetTool;
			this._toolChanged.fire(targetTool);
		}

		const newPoint: FibPoint = {
			time: point.time,
			price: point.price
		};

		if (targetTool === 'retracement') {
			if (this._pendingPoints.length >= 2) {
				this._pendingPoints = [];
			}
			this._pendingPoints.push(newPoint);

			if (this._pendingPoints.length === 2) {
				const [p1, p2] = this._pendingPoints;
				this._retracement = {
					p1,
					p2,
					levels: this._retracement?.levels ?? null,
					extendLines: this._retracement?.extendLines,
					visible: this._retracement?.visible ?? true
				};
				this._pendingPoints = [];
				this.setDrawingMode(false);
				this._drawingsChanged.fire(this.getDrawings());
			} else {
				this._drawingsChanged.fire(this.getDrawings());
			}
		} else if (targetTool === 'extension') {
			if (this._pendingPoints.length >= 3) {
				this._pendingPoints = [];
			}
			this._pendingPoints.push(newPoint);

			if (this._pendingPoints.length === 3) {
				const [p1, p2, p3] = this._pendingPoints;
				this._extension = {
					p1,
					p2,
					p3,
					levels: this._extension?.levels ?? null,
					extendLines: this._extension?.extendLines,
					visible: this._extension?.visible ?? true
				};
				this._pendingPoints = [];
				this.setDrawingMode(false);
				this._drawingsChanged.fire(this.getDrawings());
			} else {
				this._drawingsChanged.fire(this.getDrawings());
			}
		}

		return newPoint;
	}

	public updatePoint(
		tool: FibToolType,
		pointIndex: 0 | 1 | 2 | number,
		update: { time?: Time; price?: number }
	): boolean {
		if (tool === 'retracement') {
			if (!this._retracement) return false;
			const p1 = { ...this._retracement.p1 };
			const p2 = { ...this._retracement.p2 };

			if (pointIndex === 0) {
				if (update.time !== undefined) p1.time = update.time;
				if (update.price !== undefined) p1.price = update.price;
			} else if (pointIndex === 1) {
				if (update.time !== undefined) p2.time = update.time;
				if (update.price !== undefined) p2.price = update.price;
			} else {
				return false;
			}

			this._retracement = {
				...this._retracement,
				p1,
				p2
			};
			this._drawingsChanged.fire(this.getDrawings());
			return true;
		} else if (tool === 'extension') {
			if (!this._extension) return false;
			const p1 = { ...this._extension.p1 };
			const p2 = { ...this._extension.p2 };
			const p3 = { ...this._extension.p3 };

			if (pointIndex === 0) {
				if (update.time !== undefined) p1.time = update.time;
				if (update.price !== undefined) p1.price = update.price;
			} else if (pointIndex === 1) {
				if (update.time !== undefined) p2.time = update.time;
				if (update.price !== undefined) p2.price = update.price;
			} else if (pointIndex === 2) {
				if (update.time !== undefined) p3.time = update.time;
				if (update.price !== undefined) p3.price = update.price;
			} else {
				return false;
			}

			this._extension = {
				...this._extension,
				p1,
				p2,
				p3
			};
			this._drawingsChanged.fire(this.getDrawings());
			return true;
		}
		return false;
	}

	public clear(tool?: FibToolType): void {
		if (!tool || tool === 'retracement') {
			this._retracement = null;
			if (this._activeTool === 'retracement') {
				this._pendingPoints = [];
			}
		}
		if (!tool || tool === 'extension') {
			this._extension = null;
			if (this._activeTool === 'extension') {
				this._pendingPoints = [];
			}
		}
		this._drawingsChanged.fire(this.getDrawings());
	}

	public setHoveredPoint(point: FibPointTarget | null): void {
		const changed =
			this._hoveredPoint?.tool !== point?.tool ||
			this._hoveredPoint?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._hoveredPoint = point;
			this._hoverChanged.fire(point);
		}
	}

	public getHoveredPoint(): FibPointTarget | null {
		return this._hoveredPoint;
	}

	public setDraggingPoint(point: FibPointTarget | null): void {
		const changed =
			this._draggingPoint?.tool !== point?.tool ||
			this._draggingPoint?.pointIndex !== point?.pointIndex;
		if (changed) {
			this._draggingPoint = point;
			this._dragChanged.fire(point);
		}
	}

	public getDraggingPoint(): FibPointTarget | null {
		return this._draggingPoint;
	}

	public destroy(): void {
		this._drawingsChanged.destroy();
		this._drawingModeChanged.destroy();
		this._toolChanged.destroy();
		this._hoverChanged.destroy();
		this._dragChanged.destroy();
	}
}
