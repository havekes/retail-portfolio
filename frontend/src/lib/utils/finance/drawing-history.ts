import type { SecurityElliottWaves } from './elliott-wave';
import { areSecurityElliottWavesEqual } from './elliott-wave';
import type { SecurityFibonacciTools } from './fibonacci';
import { areFibonacciToolsEqual } from './fibonacci';
import type { SecurityDrawings } from './drawings';
import { areSecurityDrawingsEqual } from './drawings';

export interface SecurityDrawingState {
	elliott_waves?: SecurityElliottWaves | null;
	fibonacci_tools?: SecurityFibonacciTools | null;
	drawings?: SecurityDrawings | null;
}

export interface PushOptions {
	coalesce?: boolean;
}

export function areDrawingStatesEqual(
	a: SecurityDrawingState | null | undefined,
	b: SecurityDrawingState | null | undefined
): boolean {
	if (!a && !b) return true;
	if (!a || !b) return false;

	if (!areSecurityElliottWavesEqual(a.elliott_waves, b.elliott_waves)) {
		return false;
	}

	const aFibEmpty =
		!a.fibonacci_tools || (!a.fibonacci_tools.retracement && !a.fibonacci_tools.extension);
	const bFibEmpty =
		!b.fibonacci_tools || (!b.fibonacci_tools.retracement && !b.fibonacci_tools.extension);
	if (aFibEmpty !== bFibEmpty) return false;
	if (!aFibEmpty && !areFibonacciToolsEqual(a.fibonacci_tools, b.fibonacci_tools)) {
		return false;
	}

	if (!areSecurityDrawingsEqual(a.drawings, b.drawings)) {
		return false;
	}

	return true;
}

function cloneDrawingState(state: SecurityDrawingState): SecurityDrawingState {
	if (!state) return {};
	try {
		return JSON.parse(JSON.stringify(state));
	} catch {
		return { ...state };
	}
}

/**
 * Session history manager for chart drawing mutations (add, move/drag, delete, clear).
 * Maintains an undo stack and redo stack of drawing state snapshots.
 */
export class DrawingHistoryManager {
	private _undoStack: SecurityDrawingState[] = [];
	private _redoStack: SecurityDrawingState[] = [];
	private _isCoalescing: boolean = false;
	private readonly _maxHistory: number;

	constructor(options?: { maxHistory?: number }) {
		this._maxHistory = options?.maxHistory ?? 100;
	}

	public init(initialState: SecurityDrawingState): void {
		this._undoStack = [cloneDrawingState(initialState)];
		this._redoStack = [];
		this._isCoalescing = false;
	}

	public canUndo(): boolean {
		return this._undoStack.length > 1;
	}

	public canRedo(): boolean {
		return this._redoStack.length > 0;
	}

	public startCoalescing(): void {
		this._isCoalescing = true;
	}

	public stopCoalescing(): void {
		this._isCoalescing = false;
	}

	public isCoalescing(): boolean {
		return this._isCoalescing;
	}

	public push(state: SecurityDrawingState, options?: PushOptions | boolean): void {
		const shouldCoalesce =
			typeof options === 'boolean' ? options : Boolean(options?.coalesce) || this._isCoalescing;

		const current = this._undoStack[this._undoStack.length - 1];
		if (current && areDrawingStatesEqual(state, current)) {
			return;
		}

		if (shouldCoalesce && this._undoStack.length > 1) {
			this._undoStack[this._undoStack.length - 1] = cloneDrawingState(state);
		} else {
			this._undoStack.push(cloneDrawingState(state));
			if (this._undoStack.length > this._maxHistory) {
				this._undoStack.shift();
			}
		}

		this._redoStack = [];
	}

	public undo(): SecurityDrawingState | null {
		if (!this.canUndo()) return null;
		const current = this._undoStack.pop()!;
		this._redoStack.push(current);
		this._isCoalescing = false;
		return cloneDrawingState(this._undoStack[this._undoStack.length - 1]);
	}

	public redo(): SecurityDrawingState | null {
		if (!this.canRedo()) return null;
		const next = this._redoStack.pop()!;
		this._undoStack.push(next);
		this._isCoalescing = false;
		return cloneDrawingState(next);
	}

	public getCurrentState(): SecurityDrawingState | null {
		if (this._undoStack.length === 0) return null;
		return cloneDrawingState(this._undoStack[this._undoStack.length - 1]);
	}

	public clear(): void {
		this._undoStack = [];
		this._redoStack = [];
		this._isCoalescing = false;
	}
}
