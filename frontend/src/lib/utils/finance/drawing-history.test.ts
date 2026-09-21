import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
	DrawingHistoryManager,
	areDrawingStatesEqual,
	type SecurityDrawingState
} from './drawing-history';
import type { Time } from 'lightweight-charts';

describe('DrawingHistoryManager', () => {
	let manager: DrawingHistoryManager;

	const emptyState: SecurityDrawingState = {
		elliott_waves: { waves: [] },
		fibonacci_tools: {},
		drawings: { horizontalLines: [], lines: [], measures: [] }
	};

	const stateWithLine: SecurityDrawingState = {
		elliott_waves: { waves: [] },
		fibonacci_tools: {},
		drawings: {
			horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price: 100 } }],
			lines: [],
			measures: []
		}
	};

	const stateWithLineMoved: SecurityDrawingState = {
		elliott_waves: { waves: [] },
		fibonacci_tools: {},
		drawings: {
			horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price: 105 } }],
			lines: [],
			measures: []
		}
	};

	const stateWithTwoLines: SecurityDrawingState = {
		elliott_waves: { waves: [] },
		fibonacci_tools: {},
		drawings: {
			horizontalLines: [
				{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price: 105 } },
				{ id: 'hl-2', p1: { time: '2024-01-02' as Time, price: 110 } }
			],
			lines: [],
			measures: []
		}
	};

	beforeEach(() => {
		manager = new DrawingHistoryManager();
		manager.init(emptyState);
	});

	it('initializes with base state, canUndo and canRedo false', () => {
		expect(manager.canUndo()).toBe(false);
		expect(manager.canRedo()).toBe(false);
		expect(manager.getCurrentState()).toEqual(emptyState);
	});

	it('pushes mutations and enables undo', () => {
		manager.push(stateWithLine);
		expect(manager.canUndo()).toBe(true);
		expect(manager.canRedo()).toBe(false);
		expect(manager.getCurrentState()).toEqual(stateWithLine);
	});

	it('reverts mutations on undo and enables redo', () => {
		manager.push(stateWithLine);
		manager.push(stateWithTwoLines);

		expect(manager.canUndo()).toBe(true);
		const undone = manager.undo();
		expect(undone).toEqual(stateWithLine);
		expect(manager.canUndo()).toBe(true);
		expect(manager.canRedo()).toBe(true);

		const undoneBase = manager.undo();
		expect(undoneBase).toEqual(emptyState);
		expect(manager.canUndo()).toBe(false);
		expect(manager.canRedo()).toBe(true);
	});

	it('re-applies mutations on redo', () => {
		manager.push(stateWithLine);
		manager.push(stateWithTwoLines);

		manager.undo();
		manager.undo();

		const redone = manager.redo();
		expect(redone).toEqual(stateWithLine);
		expect(manager.canUndo()).toBe(true);
		expect(manager.canRedo()).toBe(true);

		const redone2 = manager.redo();
		expect(redone2).toEqual(stateWithTwoLines);
		expect(manager.canUndo()).toBe(true);
		expect(manager.canRedo()).toBe(false);
	});

	it('clears redo stack when a new mutation is pushed after undo', () => {
		manager.push(stateWithLine);
		manager.undo();
		expect(manager.canRedo()).toBe(true);

		manager.push(stateWithLineMoved);
		expect(manager.canRedo()).toBe(false);
		expect(manager.getCurrentState()).toEqual(stateWithLineMoved);
	});

	it('deduplicates identical state pushes', () => {
		manager.push(stateWithLine);
		manager.push(stateWithLine);
		expect(manager.canUndo()).toBe(true);
		manager.undo();
		expect(manager.canUndo()).toBe(false);
	});

	it('coalesces rapid drag movements into a single undo step', () => {
		manager.push(stateWithLine);

		// Dragging hl-1: intermediate positions pushed with coalesce = true
		manager.push(stateWithLineMoved, { coalesce: true });

		const stateWithLineMovedFurther: SecurityDrawingState = {
			elliott_waves: { waves: [] },
			fibonacci_tools: {},
			drawings: {
				horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price: 115 } }],
				lines: [],
				measures: []
			}
		};
		manager.push(stateWithLineMovedFurther, { coalesce: true });

		// Undoing the drag reverts to the pre-drag state (stateWithLine)
		expect(manager.canUndo()).toBe(true);
		const undone = manager.undo();
		expect(undone).toEqual(stateWithLine);
		expect(manager.canUndo()).toBe(true);

		// Redo should jump to the final dragged position
		const redone = manager.redo();
		expect(redone).toEqual(stateWithLineMovedFurther);

		// Subsequent undo calls revert to pre-drag state, then back to base emptyState
		expect(manager.undo()).toEqual(stateWithLine);
		expect(manager.undo()).toEqual(emptyState);
		expect(manager.canUndo()).toBe(false);
	});

	it('supports startCoalescing and stopCoalescing flags', () => {
		manager.push(stateWithLine);

		manager.startCoalescing();
		expect(manager.isCoalescing()).toBe(true);
		manager.push(stateWithLineMoved);

		const stateWithLineMovedFurther: SecurityDrawingState = {
			elliott_waves: { waves: [] },
			fibonacci_tools: {},
			drawings: {
				horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price: 120 } }],
				lines: [],
				measures: []
			}
		};
		manager.push(stateWithLineMovedFurther);
		manager.stopCoalescing();
		expect(manager.isCoalescing()).toBe(false);

		expect(manager.undo()).toEqual(stateWithLine);
		expect(manager.undo()).toEqual(emptyState);
	});

	it('bypasses JSON serialization during intermediate coalescing moves and clones once on stopCoalescing (AC 4, AC 5)', () => {
		manager.push(stateWithLine);

		const stringifySpy = vi.spyOn(JSON, 'stringify');

		manager.startCoalescing();

		// Intermediate drag moves: 10 rapid pushes
		for (let price = 101; price <= 110; price++) {
			manager.push({
				elliott_waves: { waves: [] },
				fibonacci_tools: {},
				drawings: {
					horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price } }],
					lines: [],
					measures: []
				}
			});
		}

		// Intermediate moves should cause ZERO JSON.stringify serialization calls
		expect(stringifySpy).toHaveBeenCalledTimes(0);

		// Stopping coalescing flushes and performs exactly 1 serialization clone
		manager.stopCoalescing();
		expect(stringifySpy).toHaveBeenCalledTimes(1);

		stringifySpy.mockRestore();

		// Pre-drag state is restored on undo, and final dragged state on redo
		expect(manager.undo()).toEqual(stateWithLine);
		const redone = manager.redo();
		expect(redone?.drawings?.horizontalLines?.[0]?.p1?.price).toBe(110);
	});

	it('bypasses JSON serialization during intermediate moves when options.coalesce is true and flushes on undo (AC 4, AC 5)', () => {
		manager.push(stateWithLine);

		const stringifySpy = vi.spyOn(JSON, 'stringify');

		for (let price = 101; price <= 105; price++) {
			manager.push(
				{
					elliott_waves: { waves: [] },
					fibonacci_tools: {},
					drawings: {
						horizontalLines: [{ id: 'hl-1', p1: { time: '2024-01-01' as Time, price } }],
						lines: [],
						measures: []
					}
				},
				{ coalesce: true }
			);
		}

		// 0 serialization calls during intermediate moves
		expect(stringifySpy).toHaveBeenCalledTimes(0);

		// Undoing flushes the coalesced state first (1 clone on flush into _undoStack, 1 clone returning the undone state)
		const undone = manager.undo();
		expect(undone).toEqual(stateWithLine);

		const redone = manager.redo();
		expect(redone?.drawings?.horizontalLines?.[0]?.p1?.price).toBe(105);

		stringifySpy.mockRestore();
	});

	it('notifies subscribers on init, push, undo, redo, and clear, and allows unsubscribe', () => {
		let callCount = 0;
		const unsubscribe = manager.subscribe(() => {
			callCount++;
		});

		manager.push(stateWithLine);
		expect(callCount).toBe(1);

		// Duplicate push should not notify
		manager.push(stateWithLine);
		expect(callCount).toBe(1);

		manager.undo();
		expect(callCount).toBe(2);

		manager.redo();
		expect(callCount).toBe(3);

		manager.init(emptyState);
		expect(callCount).toBe(4);

		manager.clear();
		expect(callCount).toBe(5);

		// Unsubscribe stops notifications
		unsubscribe();
		manager.push(stateWithLine);
		expect(callCount).toBe(5);
	});
});

describe('areDrawingStatesEqual', () => {
	it('treats identical empty states as equal', () => {
		expect(areDrawingStatesEqual({}, {})).toBe(true);
		expect(areDrawingStatesEqual(null, null)).toBe(true);
		expect(areDrawingStatesEqual(undefined, undefined)).toBe(true);
	});

	it('detects differences in drawings', () => {
		const a: SecurityDrawingState = {
			drawings: { horizontalLines: [{ id: '1', p1: { time: '2024-01-01' as Time, price: 10 } }] }
		};
		const b: SecurityDrawingState = {
			drawings: { horizontalLines: [{ id: '1', p1: { time: '2024-01-01' as Time, price: 20 } }] }
		};
		expect(areDrawingStatesEqual(a, b)).toBe(false);
	});

	it('detects differences in waves', () => {
		const a: SecurityDrawingState = {
			elliott_waves: {
				waves: [{ id: 'w1', degree: 'cycle', type: 'impulse', points: [] }]
			}
		};
		const b: SecurityDrawingState = {
			elliott_waves: { waves: [] }
		};
		expect(areDrawingStatesEqual(a, b)).toBe(false);
	});
});
