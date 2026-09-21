import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import {
	ChartDrawingsService,
	type ChartInstance,
	type UserPreferencesServiceLike,
	type SnapshotsServiceLike,
	type ToastLike
} from './ChartDrawingsService.svelte';
import type { Time } from 'lightweight-charts';
import type { Candle } from '@/utils/finance/candle';
import type { UserPreferences } from '$lib/api/userPreferencesService';
import type {
	LineDrawing,
	MeasureDrawing,
	HorizontalLineDrawing
} from '$lib/utils/finance/drawings';
import type { RewindSnapshot } from '$lib/utils/finance/rewind';

describe('ChartDrawingsService', () => {
	let mockPatchPreferences: Mock<UserPreferencesServiceLike['patchPreferences']>;
	let mockCreateSnapshot: Mock<SnapshotsServiceLike['createSnapshot']>;
	let mockGetSnapshots: Mock<SnapshotsServiceLike['getSnapshots']>;
	let mockToast: {
		info: Mock<ToastLike['info']>;
		success: Mock<ToastLike['success']>;
		error: Mock<ToastLike['error']>;
	};
	let mockWaveAlertsReconcile: Mock<() => void>;
	let mockPreferencesChanged: Mock<(prefs: UserPreferences) => void>;
	let mockChartSettingsOpen: Mock<() => void>;

	const sampleCandles: Candle[] = [
		{
			time: '2025-01-01' as unknown as Time,
			open: 100,
			high: 105,
			low: 99,
			close: 104,
			volume: 1000
		},
		{
			time: '2025-01-02' as unknown as Time,
			open: 104,
			high: 110,
			low: 103,
			close: 108,
			volume: 1500
		}
	];

	beforeEach(() => {
		mockPatchPreferences = vi.fn().mockResolvedValue({} as UserPreferences);
		mockCreateSnapshot = vi.fn().mockImplementation((_secId, req) =>
			Promise.resolve({
				id: 'snap-1',
				security_id: _secId,
				captured_at: req.captured_at ?? new Date().toISOString(),
				drawings: req.drawings,
				data_window: req.data_window
			})
		);
		mockGetSnapshots = vi.fn().mockResolvedValue([]);
		mockToast = {
			info: vi.fn(),
			success: vi.fn(),
			error: vi.fn()
		};
		mockWaveAlertsReconcile = vi.fn();
		mockPreferencesChanged = vi.fn();
		mockChartSettingsOpen = vi.fn();
	});

	function createService(
		overrides: Partial<ConstructorParameters<typeof ChartDrawingsService>[0]> = {}
	) {
		return new ChartDrawingsService({
			securityId: 'sec-1',
			userPreferences: {},
			displayCandles: sampleCandles,
			userPreferencesService: {
				patchPreferences: mockPatchPreferences
			},
			snapshotsService: {
				createSnapshot: mockCreateSnapshot,
				getSnapshots: mockGetSnapshots
			},
			toast: mockToast,
			onWaveAlertsReconcile: mockWaveAlertsReconcile,
			onPreferencesChanged: mockPreferencesChanged,
			onChartSettingsOpen: mockChartSettingsOpen,
			...overrides
		});
	}

	describe('Tool activation and mutual exclusion', () => {
		it('activates wave drawing and mutually excludes other tools', () => {
			const service = createService();
			service.selectWaveDegree('primary', 'impulse');

			expect(service.isDrawingWave).toBe(true);
			expect(service.activeWaveDegree).toBe('primary');
			expect(service.activeWaveType).toBe('impulse');
			expect(service.isDrawingFib).toBe(false);
			expect(service.isDrawingMeasure).toBe(false);
			expect(service.isDrawingHorizontalLine).toBe(false);
			expect(service.isDrawingLine).toBe(false);
		});

		it('activates Fibonacci retracement and clears wave drawing', () => {
			const service = createService();
			service.selectWaveDegree('cycle');
			expect(service.isDrawingWave).toBe(true);

			service.toggleFib('retracement');
			expect(service.isDrawingFib).toBe(true);
			expect(service.activeFibTool).toBe('retracement');
			expect(service.isDrawingWave).toBe(false);

			// Toggling again deactivates it
			service.toggleFib('retracement');
			expect(service.isDrawingFib).toBe(false);
		});

		it('activates Measure tool and clears other tools and selections', () => {
			const service = createService();
			service.toggleFib('extension');
			service.selectedFibTool = 'extension';

			service.toggleMeasure();
			expect(service.isDrawingMeasure).toBe(true);
			expect(service.isDrawingFib).toBe(false);
			expect(service.selectedFibTool).toBeNull();

			// Toggling again deactivates
			service.toggleMeasure();
			expect(service.isDrawingMeasure).toBe(false);
		});

		it('activates Horizontal Line tool and Line tool with mutual exclusion', () => {
			const service = createService();
			service.toggleHorizontalLine();
			expect(service.isDrawingHorizontalLine).toBe(true);
			expect(service.isDrawingLine).toBe(false);

			service.toggleLine();
			expect(service.isDrawingLine).toBe(true);
			expect(service.isDrawingHorizontalLine).toBe(false);

			service.toggleLine();
			expect(service.isDrawingLine).toBe(false);
		});

		it('handles drawing mode changes emitted by ChartComponent', () => {
			const service = createService();
			service.setDrawingMeasureMode(true);
			expect(service.isDrawingMeasure).toBe(true);
			expect(service.isDrawingLine).toBe(false);

			service.setDrawingLineMode(true);
			expect(service.isDrawingLine).toBe(true);
			expect(service.isDrawingMeasure).toBe(false);

			service.setDrawingWaveMode(true);
			expect(service.isDrawingWave).toBe(true);
			expect(service.isDrawingLine).toBe(false);

			service.setDrawingFibMode(true);
			expect(service.isDrawingFib).toBe(true);
			expect(service.isDrawingWave).toBe(false);

			service.setDrawingHorizontalLineMode(true);
			expect(service.isDrawingHorizontalLine).toBe(true);
			expect(service.isDrawingFib).toBe(false);
		});
	});

	describe('Deletion via Delete and Backspace keys', () => {
		it('deletes selected measure on Delete key', async () => {
			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': {
							measures: [
								{
									id: 'm1',
									p1: { time: '2025-01-01' as unknown as Time, price: 100 },
									p2: { time: '2025-01-02' as unknown as Time, price: 110 }
								} as MeasureDrawing
							],
							horizontalLines: [],
							lines: []
						}
					}
				}
			});

			service.selectedMeasureId = 'm1';
			const event = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
			service.handleKeyDown(event);

			expect(service.selectedMeasureId).toBeNull();
			expect(mockPatchPreferences).toHaveBeenCalledWith({
				drawings: {
					'sec-1': {
						measures: null,
						horizontalLines: [],
						lines: []
					}
				}
			});
		});

		it('deletes selected horizontal line on Backspace key', async () => {
			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': {
							measures: [],
							horizontalLines: [{ id: 'h1', price: 105 } as unknown as HorizontalLineDrawing],
							lines: []
						}
					}
				}
			});

			service.selectedHorizontalLineId = 'h1';
			const event = new KeyboardEvent('keydown', { key: 'Backspace', cancelable: true });
			service.handleKeyDown(event);

			expect(service.selectedHorizontalLineId).toBeNull();
			expect(mockPatchPreferences).toHaveBeenCalledWith({
				drawings: {
					'sec-1': {
						measures: [],
						horizontalLines: null,
						lines: []
					}
				}
			});
		});

		it('deletes selected line on Delete key', async () => {
			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': {
							measures: [],
							horizontalLines: [],
							lines: [
								{
									id: 'l1',
									p1: { time: '2025-01-01' as unknown as Time, price: 100 },
									p2: { time: '2025-01-02' as unknown as Time, price: 110 }
								} as LineDrawing
							]
						}
					}
				}
			});

			service.selectedLineId = 'l1';
			const event = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
			service.handleKeyDown(event);

			expect(service.selectedLineId).toBeNull();
			expect(mockPatchPreferences).toHaveBeenCalledWith({
				drawings: {
					'sec-1': {
						measures: [],
						horizontalLines: [],
						lines: null
					}
				}
			});
		});

		it('clears selected Fibonacci tool on Delete key', async () => {
			const service = createService({
				userPreferences: {
					fibonacci_tools: {
						'sec-1': {
							retracement: {
								p1: { time: '2025-01-01' as unknown as Time, price: 100 },
								p2: { time: '2025-01-02' as unknown as Time, price: 110 },
								levels: []
							},
							extension: null
						}
					}
				}
			});

			service.selectedFibTool = 'retracement';
			const event = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
			service.handleKeyDown(event);

			expect(service.selectedFibTool).toBeNull();
			expect(mockPatchPreferences).toHaveBeenCalledWith({
				fibonacci_tools: {
					'sec-1': {
						retracement: null,
						extension: null
					}
				}
			});
		});

		it('clears wave via chartRef on Delete key when wave is selected', async () => {
			const clearWave = vi.fn();
			const mockChartRef = {
				clearWave,
				getSelectedWaveId: () => 'wave-1',
				getSelectedWaveDegree: () => 'primary' as const
			} as unknown as ChartInstance;

			const service = createService({
				getChartRef: () => mockChartRef
			});

			service.selectedWaveDegree = 'primary';
			const event = new KeyboardEvent('keydown', { key: 'Delete', cancelable: true });
			service.handleKeyDown(event, mockChartRef);

			expect(clearWave).toHaveBeenCalledWith('wave-1');
			expect(service.selectedWaveDegree).toBeNull();
		});

		it('does not trigger deletion when typing inside an input element', () => {
			const service = createService();
			service.selectedLineId = 'l1';

			const input = document.createElement('input');
			const event = new KeyboardEvent('keydown', { key: 'Delete' });
			Object.defineProperty(event, 'target', { value: input, writable: false });

			service.handleKeyDown(event);
			expect(service.selectedLineId).toBe('l1');
			expect(mockPatchPreferences).not.toHaveBeenCalled();
		});
	});

	describe('Escape tool cancellation', () => {
		it('cancels active drawing mode and clears selections on Escape', () => {
			const service = createService();
			service.isDrawingLine = true;
			service.selectedLineId = 'l1';

			const event = new KeyboardEvent('keydown', { key: 'Escape' });
			service.handleKeyDown(event);

			expect(service.isDrawingLine).toBe(false);
			expect(service.selectedLineId).toBeNull();
		});

		it('cancelActiveDrawing resets all drawing flags and selections', () => {
			const service = createService();
			service.isDrawingWave = true;
			service.isDrawingFib = true;
			service.selectedWaveDegree = 'cycle';
			service.selectedFibTool = 'retracement';

			service.cancelActiveDrawing();

			expect(service.isDrawingWave).toBe(false);
			expect(service.isDrawingFib).toBe(false);
			expect(service.selectedWaveDegree).toBeNull();
			expect(service.selectedFibTool).toBeNull();
		});
	});

	describe('Undo and Redo orchestration', () => {
		it('records state transitions and restores them on undo and redo', async () => {
			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': { measures: [], horizontalLines: [], lines: [] }
					}
				}
			});

			const line1: LineDrawing = {
				id: 'l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 100 },
				p2: { time: '2025-01-02' as unknown as Time, price: 110 }
			};

			const line2: LineDrawing = {
				id: 'l2',
				p1: { time: '2025-01-01' as unknown as Time, price: 105 },
				p2: { time: '2025-01-02' as unknown as Time, price: 115 }
			};

			// 1. Add line1
			await service.handleLineChange([line1]);
			expect(service.canUndo).toBe(true);
			expect(service.canRedo).toBe(false);
			expect(mockPatchPreferences).toHaveBeenCalledTimes(1);

			// 2. Add line2
			await service.handleLineChange([line1, line2]);
			expect(mockPatchPreferences).toHaveBeenCalledTimes(2);

			// 3. Undo: reverts back to line1
			mockPatchPreferences.mockClear();
			await service.handleUndo();
			expect(mockPatchPreferences).toHaveBeenCalledWith(
				expect.objectContaining({
					drawings: expect.objectContaining({
						'sec-1': expect.objectContaining({
							lines: [line1]
						})
					})
				})
			);
			expect(service.canUndo).toBe(true);
			expect(service.canRedo).toBe(true);

			// 4. Redo: reapplies line2
			mockPatchPreferences.mockClear();
			await service.handleRedo();
			expect(mockPatchPreferences).toHaveBeenCalledWith(
				expect.objectContaining({
					drawings: expect.objectContaining({
						'sec-1': expect.objectContaining({
							lines: [line1, line2]
						})
					})
				})
			);
			expect(service.canRedo).toBe(false);
		});

		it('handles keyboard shortcuts for undo and redo', async () => {
			const service = createService();
			const undoSpy = vi.spyOn(service, 'handleUndo');
			const redoSpy = vi.spyOn(service, 'handleRedo');

			// Ctrl+Z
			service.handleKeyDown(
				new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, cancelable: true })
			);
			expect(undoSpy).toHaveBeenCalledTimes(1);

			// Ctrl+Shift+Z
			service.handleKeyDown(
				new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, shiftKey: true, cancelable: true })
			);
			expect(redoSpy).toHaveBeenCalledTimes(1);

			// Ctrl+Y
			service.handleKeyDown(
				new KeyboardEvent('keydown', { key: 'y', ctrlKey: true, cancelable: true })
			);
			expect(redoSpy).toHaveBeenCalledTimes(2);
		});
	});

	describe('Dragging preference coalescing', () => {
		it('defers preference patch calls during drag and commits once on drag end', async () => {
			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': { measures: [], horizontalLines: [], lines: [] }
					}
				}
			});

			const baseLine: LineDrawing = {
				id: 'l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 100 },
				p2: { time: '2025-01-02' as unknown as Time, price: 110 }
			};

			// Initial change commits immediately
			await service.handleLineChange([baseLine]);
			expect(mockPatchPreferences).toHaveBeenCalledTimes(1);
			mockPatchPreferences.mockClear();

			// Drag starts
			service.handleDrawingDragStart();
			expect(service.isDraggingDrawing).toBe(true);

			// Intermediate moves
			const moved1: LineDrawing = { ...baseLine, p2: { ...baseLine.p2, price: 112 } };
			const moved2: LineDrawing = { ...baseLine, p2: { ...baseLine.p2, price: 118 } };
			await service.handleLineChange([moved1]);
			await service.handleLineChange([moved2]);

			expect(mockPatchPreferences).not.toHaveBeenCalled();

			// Drag ends
			await service.handleDrawingDragEnd();
			expect(service.isDraggingDrawing).toBe(false);
			expect(mockPatchPreferences).toHaveBeenCalledTimes(1);
			expect(mockPatchPreferences).toHaveBeenCalledWith({
				drawings: {
					'sec-1': {
						measures: [],
						horizontalLines: [],
						lines: [moved2]
					}
				}
			});
		});

		it('does not emit patchPreferences if drag ends without moves', async () => {
			const service = createService();
			service.handleDrawingDragStart();
			await service.handleDrawingDragEnd();

			expect(mockPatchPreferences).not.toHaveBeenCalled();
		});
	});

	describe('Snapshots management and rewind', () => {
		it('captures and saves snapshot via snapshotsService', async () => {
			const line: LineDrawing = {
				id: 'l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 100 },
				p2: { time: '2025-01-02' as unknown as Time, price: 110 }
			};

			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': { measures: [], horizontalLines: [], lines: [line] }
					}
				}
			});

			await service.handleSaveSnapshot();

			expect(mockCreateSnapshot).toHaveBeenCalledTimes(1);
			expect(mockCreateSnapshot).toHaveBeenCalledWith(
				'sec-1',
				expect.objectContaining({
					drawings: expect.objectContaining({
						drawings: {
							measures: [],
							horizontalLines: [],
							lines: [line]
						}
					}),
					data_window: {
						first: '2025-01-01',
						last: '2025-01-02'
					}
				})
			);

			expect(service.snapshots.length).toBe(1);
			expect(service.isTimelineVisible).toBe(true);
			expect(service.saveFeedback).toBe('saved');
			expect(mockToast.success).toHaveBeenCalledWith('Chart snapshot saved');
		});

		it('does not save snapshot if drawings are empty', async () => {
			const service = createService({
				userPreferences: {}
			});

			await service.handleSaveSnapshot();
			expect(mockCreateSnapshot).not.toHaveBeenCalled();
		});

		it('informs user if snapshot is identical to the last one', async () => {
			const line: LineDrawing = {
				id: 'l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 100 },
				p2: { time: '2025-01-02' as unknown as Time, price: 110 }
			};

			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': { measures: [], horizontalLines: [], lines: [line] }
					}
				}
			});

			await service.handleSaveSnapshot();
			expect(mockCreateSnapshot).toHaveBeenCalledTimes(1);

			// Saving again without drawing change
			await service.handleSaveSnapshot();
			expect(mockCreateSnapshot).toHaveBeenCalledTimes(1);
			expect(mockToast.info).toHaveBeenCalledWith('Chart snapshot already up to date');
		});

		it('returns active snapshot drawings when rewound', () => {
			const liveLine: LineDrawing = {
				id: 'live-l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 100 },
				p2: { time: '2025-01-02' as unknown as Time, price: 110 }
			};
			const snapLine: LineDrawing = {
				id: 'snap-l1',
				p1: { time: '2025-01-01' as unknown as Time, price: 90 },
				p2: { time: '2025-01-02' as unknown as Time, price: 95 }
			};

			const snapshot: RewindSnapshot = {
				id: 'snap-1',
				security_id: 'sec-1',
				captured_at: '2025-01-02T00:00:00.000Z',
				drawings: {
					elliott_waves: { waves: [] },
					fibonacci_tools: {},
					drawings: { measures: [], horizontalLines: [], lines: [snapLine] }
				},
				data_window: { first: '2025-01-01', last: '2025-01-02' }
			};

			const service = createService({
				userPreferences: {
					drawings: {
						'sec-1': { measures: [], horizontalLines: [], lines: [liveLine] }
					}
				}
			});

			service.snapshots = [snapshot];

			// Not rewound: effective drawings are live drawings
			expect(service.effectiveSecurityDrawings.lines).toEqual([liveLine]);
			expect(service.getEffectiveSecurityDrawings().lines).toEqual([liveLine]);

			// Rewound to the snapshot time
			service.setTimelinePosition(new Date('2025-01-02T12:00:00.000Z'));
			expect(service.isRewound).toBe(true);
			expect(service.effectiveSecurityDrawings.lines).toEqual([snapLine]);
			expect(service.getEffectiveSecurityDrawings().lines).toEqual([snapLine]);
		});
	});
});
