import { getContext, setContext } from 'svelte';
import type { Time } from 'lightweight-charts';
import type { Candle } from '@/utils/finance/candle';
import type { UserPreferences } from '$lib/api/userPreferencesService';
import { userPreferencesService } from '$lib/api/userPreferencesService';
import { snapshotsService } from '$lib/api/snapshotsService';
import { toast } from '$lib/components/ui/toast/index.js';
import type {
	DegreeWaveCount,
	SecurityElliottWaves,
	WaveDegree,
	WaveType
} from '$lib/utils/finance/elliott-wave';
import { updateSecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import type {
	FibToolType,
	FibLevelConfig,
	SecurityFibonacciTools
} from '$lib/utils/finance/fibonacci';
import { updateSecurityFibonacciTools } from '$lib/utils/finance/fibonacci';
import type {
	HorizontalLineDrawing,
	LineDrawing,
	MeasureDrawing,
	SecurityDrawings
} from '$lib/utils/finance/drawings';
import {
	isSecurityDrawingsEmpty,
	normalizeSecurityDrawings,
	removeSecurityDrawings,
	updateSecurityDrawings
} from '$lib/utils/finance/drawings';
import {
	captureSnapshot,
	areSnapshotsEqual,
	findSnapshotAtOrBefore,
	type RewindDrawings,
	type RewindDataWindow,
	type RewindSnapshot
} from '$lib/utils/finance/rewind';
import {
	DrawingHistoryManager,
	type SecurityDrawingState
} from '$lib/utils/finance/drawing-history';
import type { IndicatorData } from '$lib/components/charts/security-chart.svelte';

export interface ChartInstance {
	addIndicator: (indicator: IndicatorData) => void;
	removeIndicator: (indicatorId: string) => void;
	clearWave?: (waveIdOrDegree?: string | WaveDegree) => void;
	getSelectedWaveDegree?: () => WaveDegree | null;
	getSelectedWaveId?: () => string | null;
	getSelectedFibTool?: () => FibToolType | null;
	getSelectedMeasureId?: () => string | null;
	getSelectedHorizontalLineId?: () => string | null;
	getSelectedLineId?: () => string | null;
	setPaneHeights?: (heights: Record<string, number> | null) => void;
	[key: string]: unknown;
}

export interface UserPreferencesServiceLike {
	patchPreferences: (patch: Partial<UserPreferences>) => Promise<UserPreferences>;
}

export interface SnapshotsServiceLike {
	createSnapshot: (
		securityId: string,
		req: {
			drawings: RewindDrawings;
			data_window: RewindDataWindow;
			captured_at?: string;
		}
	) => Promise<RewindSnapshot>;
	getSnapshots: (securityId: string) => Promise<RewindSnapshot[]>;
}

export interface ToastLike {
	info: (msg: string) => void;
	success: (msg: string) => void;
	error: (msg: string) => void;
}

export interface ChartDrawingsServiceOptions {
	securityId?: string | null;
	userPreferences?: UserPreferences | null;
	displayCandles?: Candle[];
	getChartRef?: () => ChartInstance | null;
	onWaveAlertsReconcile?: () => Promise<void> | void;
	onPreferencesChanged?: (prefs: UserPreferences) => void;
	onChartSettingsOpen?: () => void;
	userPreferencesService?: UserPreferencesServiceLike;
	snapshotsService?: SnapshotsServiceLike;
	toast?: ToastLike;
}

function normalizeCandleTime(t: Time): string | number {
	if (typeof t === 'string' || typeof t === 'number') return t;
	if (typeof t === 'object' && t !== null && 'year' in t) {
		return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
	}
	return String(t);
}

/**
 * Normalizes legacy drawing anchors (date strings / `BusinessDay` objects) for
 * every security at the preference-loading seam, so restored drawings already
 * equal the epoch anchors the chart primitives derive on feed-in. Without this
 * the primitive sync effects see a difference and write one extra preference
 * patch per tool on first load.
 */
function normalizeDrawingsPreferences(prefs: UserPreferences | null): UserPreferences | null {
	if (!prefs?.drawings) return prefs;
	const drawings: Record<string, SecurityDrawings> = {};
	for (const [securityKey, value] of Object.entries(prefs.drawings)) {
		drawings[securityKey] = normalizeSecurityDrawings(value) ?? {};
	}
	return { ...prefs, drawings };
}

export class ChartDrawingsService {
	// Active tool state
	activeWaveDegree = $state<WaveDegree>('cycle');
	activeWaveType = $state<'impulse' | 'corrective'>('impulse');
	isDrawingWave = $state(false);
	activeFibTool = $state<FibToolType>('retracement');
	isDrawingFib = $state(false);
	isDrawingMeasure = $state(false);
	isDrawingHorizontalLine = $state(false);
	isDrawingLine = $state(false);

	// Selections
	selectedWaveDegree = $state<WaveDegree | null>(null);
	selectedFibTool = $state<FibToolType | null>(null);
	selectedMeasureId = $state<string | null>(null);
	selectedHorizontalLineId = $state<string | null>(null);
	selectedLineId = $state<string | null>(null);

	// Context & data
	securityId = $state<string | null>(null);
	userPreferences = $state<UserPreferences | null>(null);
	displayCandles = $state<Candle[]>([]);

	// Rewind & snapshot state
	snapshots = $state<RewindSnapshot[]>([]);
	isTimelineVisible = $state(false);
	timelinePosition = $state<Date | null>(null);
	saveFeedback = $state<'idle' | 'saved'>('idle');

	// History & drag state
	isDraggingDrawing = $state(false);
	private _canUndo = $state(false);
	private _canRedo = $state(false);
	private _historyManager: DrawingHistoryManager;
	private _pendingDrawingPreferences: Partial<UserPreferences> | null = null;
	private _isApplyingHistory = false;
	private _saveFeedbackTimer: ReturnType<typeof setTimeout> | null = null;
	private _unsubscribeHistory: (() => void) | null = null;

	// Injected services & callbacks
	private options: ChartDrawingsServiceOptions;
	private _userPreferencesService: UserPreferencesServiceLike;
	private _snapshotsService: SnapshotsServiceLike;
	private _toast: ToastLike;

	// Derived properties
	get isRewound(): boolean {
		return this.timelinePosition !== null;
	}

	get securityElliottWaves(): SecurityElliottWaves {
		return (
			(this.securityId && this.userPreferences?.elliott_waves?.[this.securityId]) || { waves: [] }
		);
	}

	get securityFibonacciTools(): SecurityFibonacciTools {
		return (this.securityId && this.userPreferences?.fibonacci_tools?.[this.securityId]) || {};
	}

	get securityDrawings(): SecurityDrawings {
		const stored = (this.securityId && this.userPreferences?.drawings?.[this.securityId]) || null;
		return normalizeSecurityDrawings(stored) ?? {};
	}

	get activeSnapshot(): RewindSnapshot | null {
		return this.isRewound && this.securityId && this.timelinePosition
			? findSnapshotAtOrBefore(this.snapshots, this.timelinePosition)
			: null;
	}

	get effectiveElliottWaves(): SecurityElliottWaves {
		return this.isRewound
			? (this.activeSnapshot?.drawings?.elliott_waves ?? { waves: [] })
			: this.securityElliottWaves;
	}

	get effectiveFibonacciTools(): SecurityFibonacciTools {
		return this.isRewound
			? (this.activeSnapshot?.drawings?.fibonacci_tools ?? {})
			: this.securityFibonacciTools;
	}

	get effectiveSecurityDrawings(): SecurityDrawings {
		return this.isRewound ? (this.activeSnapshot?.drawings?.drawings ?? {}) : this.securityDrawings;
	}

	get canUndo(): boolean {
		return !this.isRewound && this._canUndo;
	}

	get canRedo(): boolean {
		return !this.isRewound && this._canRedo;
	}

	get isDrawingWaveEffective(): boolean {
		return this.isRewound ? false : this.isDrawingWave;
	}
	get isDrawingFibEffective(): boolean {
		return this.isRewound ? false : this.isDrawingFib;
	}
	get isDrawingMeasureEffective(): boolean {
		return this.isRewound ? false : this.isDrawingMeasure;
	}
	get isDrawingHorizontalLineEffective(): boolean {
		return this.isRewound ? false : this.isDrawingHorizontalLine;
	}
	get isDrawingLineEffective(): boolean {
		return this.isRewound ? false : this.isDrawingLine;
	}

	constructor(options: ChartDrawingsServiceOptions = {}) {
		this.options = options;
		this.securityId = options.securityId ?? null;
		this.userPreferences = normalizeDrawingsPreferences(options.userPreferences ?? null);
		this.displayCandles = options.displayCandles ?? [];
		this._userPreferencesService = options.userPreferencesService ?? userPreferencesService;
		this._snapshotsService = options.snapshotsService ?? snapshotsService;
		this._toast = options.toast ?? toast;

		this._historyManager = new DrawingHistoryManager();
		this._canUndo = this._historyManager.canUndo();
		this._canRedo = this._historyManager.canRedo();

		this._unsubscribeHistory = this._historyManager.subscribe(() => {
			this._canUndo = this._historyManager.canUndo();
			this._canRedo = this._historyManager.canRedo();
		});

		if (this.userPreferences && this.securityId) {
			this._historyManager.init(this.getCurrentDrawingState());
		}
	}

	getEffectiveSecurityDrawings(): SecurityDrawings {
		return this.effectiveSecurityDrawings;
	}

	setSecurity = (id: string | null) => {
		if (this.securityId === id) return;
		this.securityId = id;
		this.resetToolState();
		if (this.userPreferences && id) {
			this._historyManager.init(this.getCurrentDrawingState());
		} else {
			this._historyManager.clear();
		}
	};

	setPreferences = (prefs: UserPreferences | null) => {
		if (this.userPreferences === prefs) return;
		const normalized = normalizeDrawingsPreferences(prefs);
		this.userPreferences = normalized;
		if (normalized && this.securityId && this._historyManager.getCurrentState() === null) {
			this._historyManager.init(this.getCurrentDrawingState());
		}
	};

	setDisplayCandles = (candles: Candle[]) => {
		this.displayCandles = candles;
	};

	setTimelinePosition = (pos: Date | null) => {
		this.timelinePosition = pos;
	};

	selectWaveDegree = (degree: WaveDegree, type: WaveType = 'impulse') => {
		if (this.isRewound) this.timelinePosition = null;
		this.activeWaveDegree = degree;
		this.activeWaveType = type;
		this.isDrawingWave = true;
		this.isDrawingFib = false;
		this.isDrawingMeasure = false;
		this.isDrawingHorizontalLine = false;
		this.isDrawingLine = false;
	};

	toggleFib = (tool: FibToolType) => {
		if (this.isRewound) this.timelinePosition = null;
		if (this.isDrawingFib && this.activeFibTool === tool) {
			this.isDrawingFib = false;
		} else {
			this.activeFibTool = tool;
			this.isDrawingFib = true;
			this.isDrawingWave = false;
			this.isDrawingMeasure = false;
			this.isDrawingHorizontalLine = false;
			this.isDrawingLine = false;
		}
	};

	toggleMeasure = () => {
		if (this.isRewound) this.timelinePosition = null;
		if (this.isDrawingMeasure) {
			this.isDrawingMeasure = false;
		} else {
			this.isDrawingMeasure = true;
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingHorizontalLine = false;
			this.isDrawingLine = false;
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedHorizontalLineId = null;
			this.selectedLineId = null;
		}
	};

	toggleHorizontalLine = () => {
		if (this.isRewound) this.timelinePosition = null;
		if (this.isDrawingHorizontalLine) {
			this.isDrawingHorizontalLine = false;
		} else {
			this.isDrawingHorizontalLine = true;
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingMeasure = false;
			this.isDrawingLine = false;
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedMeasureId = null;
			this.selectedLineId = null;
		}
	};

	toggleLine = () => {
		if (this.isRewound) this.timelinePosition = null;
		if (this.isDrawingLine) {
			this.isDrawingLine = false;
		} else {
			this.isDrawingLine = true;
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingMeasure = false;
			this.isDrawingHorizontalLine = false;
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedMeasureId = null;
			this.selectedHorizontalLineId = null;
		}
	};

	toggleTimeline = () => {
		this.isTimelineVisible = !this.isTimelineVisible;
	};

	setDrawingWaveMode = (isDrawing: boolean) => {
		if (this.isRewound) return;
		this.isDrawingWave = isDrawing;
		if (isDrawing) {
			this.isDrawingFib = false;
			this.isDrawingMeasure = false;
			this.isDrawingHorizontalLine = false;
			this.isDrawingLine = false;
		}
	};

	setDrawingFibMode = (isDrawing: boolean) => {
		if (this.isRewound) return;
		this.isDrawingFib = isDrawing;
		if (isDrawing) {
			this.isDrawingWave = false;
			this.isDrawingMeasure = false;
			this.isDrawingHorizontalLine = false;
			this.isDrawingLine = false;
		}
	};

	setDrawingMeasureMode = (isDrawing: boolean) => {
		if (this.isRewound) return;
		this.isDrawingMeasure = isDrawing;
		if (isDrawing) {
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingHorizontalLine = false;
			this.isDrawingLine = false;
		}
	};

	setDrawingHorizontalLineMode = (isDrawing: boolean) => {
		if (this.isRewound) return;
		this.isDrawingHorizontalLine = isDrawing;
		if (isDrawing) {
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingMeasure = false;
			this.isDrawingLine = false;
		}
	};

	setDrawingLineMode = (isDrawing: boolean) => {
		if (this.isRewound) return;
		this.isDrawingLine = isDrawing;
		if (isDrawing) {
			this.isDrawingWave = false;
			this.isDrawingFib = false;
			this.isDrawingMeasure = false;
			this.isDrawingHorizontalLine = false;
		}
	};

	selectWave = (degree: WaveDegree | null) => {
		this.selectedWaveDegree = degree;
		if (degree) {
			this.selectedFibTool = null;
			this.selectedMeasureId = null;
			this.selectedHorizontalLineId = null;
			this.selectedLineId = null;
		}
	};

	selectFib = (tool: FibToolType | null) => {
		this.selectedFibTool = tool;
		if (tool) {
			this.selectedWaveDegree = null;
			this.selectedMeasureId = null;
			this.selectedHorizontalLineId = null;
			this.selectedLineId = null;
		}
	};

	selectMeasure = (id: string | null) => {
		this.selectedMeasureId = id;
		if (id) {
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedHorizontalLineId = null;
			this.selectedLineId = null;
		}
	};

	selectHorizontalLine = (id: string | null) => {
		this.selectedHorizontalLineId = id;
		if (id) {
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedMeasureId = null;
			this.selectedLineId = null;
		}
	};

	selectLine = (id: string | null) => {
		this.selectedLineId = id;
		if (id) {
			this.selectedWaveDegree = null;
			this.selectedFibTool = null;
			this.selectedMeasureId = null;
			this.selectedHorizontalLineId = null;
		}
	};

	clearSelection = () => {
		this.selectedWaveDegree = null;
		this.selectedFibTool = null;
		this.selectedMeasureId = null;
		this.selectedHorizontalLineId = null;
		this.selectedLineId = null;
	};

	cancelActiveDrawing = () => {
		this.clearSelection();
		this.isDrawingWave = false;
		this.isDrawingFib = false;
		this.isDrawingMeasure = false;
		this.isDrawingHorizontalLine = false;
		this.isDrawingLine = false;
	};

	resetToolState = () => {
		this.cancelActiveDrawing();
		this.activeWaveType = 'impulse';
		this.isTimelineVisible = false;
		this.timelinePosition = null;
	};

	getCurrentDrawingState(): SecurityDrawingState {
		if (!this.securityId) {
			return {
				elliott_waves: null,
				fibonacci_tools: null,
				drawings: null
			};
		}
		return {
			elliott_waves: this.userPreferences?.elliott_waves?.[this.securityId] ?? null,
			fibonacci_tools: this.userPreferences?.fibonacci_tools?.[this.securityId] ?? null,
			drawings: this.userPreferences?.drawings?.[this.securityId] ?? null
		};
	}

	recordDrawingStateChange(options?: { coalesce?: boolean }) {
		if (this._isApplyingHistory || this.isRewound || !this.securityId) return;
		this._historyManager.push(this.getCurrentDrawingState(), options);
	}

	handleDrawingDragStart = () => {
		this.isDraggingDrawing = true;
		this._pendingDrawingPreferences = null;
		this._historyManager.startCoalescing();
	};

	handleDrawingDragEnd = async () => {
		this.isDraggingDrawing = false;
		this._historyManager.stopCoalescing();
		if (this._pendingDrawingPreferences !== null) {
			const prefsToSave = { ...this._pendingDrawingPreferences };
			this._pendingDrawingPreferences = null;
			try {
				await this._userPreferencesService.patchPreferences(prefsToSave);
			} catch (err) {
				console.error('Failed to persist drawings preference on drag end:', err);
			}
			if (prefsToSave.elliott_waves) {
				this.options.onWaveAlertsReconcile?.();
			}
		}
	};

	handleUndo = async () => {
		if (this.isRewound || !this.securityId) return;
		const previousState = this._historyManager.undo();
		if (!previousState) return;
		await this.applyRestoredDrawingState(previousState);
	};

	handleRedo = async () => {
		if (this.isRewound || !this.securityId) return;
		const nextState = this._historyManager.redo();
		if (!nextState) return;
		await this.applyRestoredDrawingState(nextState);
	};

	private async applyRestoredDrawingState(restored: SecurityDrawingState) {
		if (!this.securityId) return;
		const secId = this.securityId;

		this._isApplyingHistory = true;
		try {
			const newElliottWaves = {
				...(this.userPreferences?.elliott_waves ?? {})
			};
			if (restored.elliott_waves) {
				newElliottWaves[secId] = restored.elliott_waves;
			} else {
				delete newElliottWaves[secId];
			}

			const newFibonacciTools = {
				...(this.userPreferences?.fibonacci_tools ?? {})
			};
			if (restored.fibonacci_tools) {
				newFibonacciTools[secId] = restored.fibonacci_tools;
			} else {
				delete newFibonacciTools[secId];
			}

			const newDrawings = {
				...(this.userPreferences?.drawings ?? {})
			};
			if (restored.drawings) {
				newDrawings[secId] = restored.drawings;
			} else {
				delete newDrawings[secId];
			}

			this.userPreferences = {
				...(this.userPreferences ?? {}),
				elliott_waves: newElliottWaves,
				fibonacci_tools: newFibonacciTools,
				drawings: newDrawings
			};

			this.clearSelection();

			try {
				await this._userPreferencesService.patchPreferences({
					elliott_waves: newElliottWaves,
					fibonacci_tools: newFibonacciTools,
					drawings: newDrawings
				});
			} catch (err) {
				console.error('Failed to persist restored drawing state:', err);
			}
			this.options.onPreferencesChanged?.(this.userPreferences);
			this.options.onWaveAlertsReconcile?.();
		} finally {
			this._isApplyingHistory = false;
		}
	}

	handleWaveChange = async (
		degree: WaveDegree,
		waveCount: DegreeWaveCount | null,
		allWaves?: SecurityElliottWaves
	) => {
		if (this.isRewound || !this.securityId) return;
		const updatedAllWaves = updateSecurityElliottWaves(
			this.userPreferences?.elliott_waves,
			this.securityId,
			allWaves?.waves ?? (waveCount ? [waveCount] : [])
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			elliott_waves: updatedAllWaves
		};
		this.options.onPreferencesChanged?.(this.userPreferences);
		this.recordDrawingStateChange({ coalesce: this.isDraggingDrawing });
		if (this.isDraggingDrawing) {
			this._pendingDrawingPreferences = {
				...(this._pendingDrawingPreferences ?? {}),
				elliott_waves: updatedAllWaves
			};
			return;
		}
		try {
			await this._userPreferencesService.patchPreferences({
				elliott_waves: updatedAllWaves
			});
		} catch (err) {
			console.error('Failed to persist elliott waves preference:', err);
		}
		this.options.onWaveAlertsReconcile?.();
	};

	handleClearWave = async (degree?: WaveDegree, chartRef?: ChartInstance | null) => {
		if (this.isRewound) return;
		if (degree && this.selectedWaveDegree === degree) {
			this.selectedWaveDegree = null;
		}
		const ref = chartRef ?? this.options.getChartRef?.();
		const selectedWaveId = ref?.getSelectedWaveId?.();
		if (ref?.clearWave) {
			ref.clearWave(selectedWaveId ?? degree);
		} else if (degree) {
			const current = this.securityId
				? (this.userPreferences?.elliott_waves?.[this.securityId]?.waves ?? [])
				: [];
			const degreeIdx = current.findLastIndex((w) => w.degree === degree);
			const remaining =
				degreeIdx === -1
					? current
					: [...current.slice(0, degreeIdx), ...current.slice(degreeIdx + 1)];
			await this.handleWaveChange(degree, null, { waves: remaining });
		}
	};

	handleFibChange = async (drawings: SecurityFibonacciTools) => {
		if (this.isRewound || !this.securityId) return;
		const updatedAllTools = updateSecurityFibonacciTools(
			this.userPreferences?.fibonacci_tools,
			this.securityId,
			drawings
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			fibonacci_tools: updatedAllTools
		};
		this.recordDrawingStateChange({ coalesce: this.isDraggingDrawing });
		if (this.isDraggingDrawing) {
			this._pendingDrawingPreferences = {
				...(this._pendingDrawingPreferences ?? {}),
				fibonacci_tools: updatedAllTools
			};
			this.options.onPreferencesChanged?.(this.userPreferences);
			return;
		}
		try {
			await this._userPreferencesService.patchPreferences({
				fibonacci_tools: updatedAllTools
			});
		} catch (err) {
			console.error('Failed to persist fibonacci tools preference:', err);
		}
		this.options.onPreferencesChanged?.(this.userPreferences);
	};

	handleClearFib = async (tool?: FibToolType | null) => {
		if (this.isRewound) return;
		if (tool && this.selectedFibTool === tool) {
			this.selectedFibTool = null;
		} else if (!tool) {
			this.selectedFibTool = null;
		}
		if (!this.securityId) return;
		const currentTools = this.userPreferences?.fibonacci_tools?.[this.securityId];
		const updatedSecurityTools: SecurityFibonacciTools = {
			retracement:
				tool === 'retracement'
					? null
					: tool === 'extension'
						? (currentTools?.retracement ?? null)
						: null,
			extension:
				tool === 'extension'
					? null
					: tool === 'retracement'
						? (currentTools?.extension ?? null)
						: null
		};
		await this.handleFibChange(updatedSecurityTools);
	};

	handleFibLevelsChange = async (tool: FibToolType, levels: FibLevelConfig[]) => {
		if (this.isRewound || !this.securityId) return;
		const currentTools = this.userPreferences?.fibonacci_tools?.[this.securityId];
		let updatedSecurityTools: SecurityFibonacciTools;
		if (tool === 'retracement') {
			const currentDrawing = currentTools?.retracement;
			updatedSecurityTools = {
				...currentTools,
				retracement: currentDrawing ? { ...currentDrawing, levels } : null
			};
		} else {
			const currentDrawing = currentTools?.extension;
			updatedSecurityTools = {
				...currentTools,
				extension: currentDrawing ? { ...currentDrawing, levels } : null
			};
		}
		const updatedAllTools = updateSecurityFibonacciTools(
			this.userPreferences?.fibonacci_tools,
			this.securityId,
			updatedSecurityTools
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			fibonacci_tools: updatedAllTools
		};
		this.recordDrawingStateChange();
		try {
			await this._userPreferencesService.patchPreferences({
				fibonacci_tools: updatedAllTools
			});
		} catch (err) {
			console.error('Failed to persist fibonacci tools preference:', err);
		}
		this.options.onPreferencesChanged?.(this.userPreferences);
	};

	handleFibWidthSave = async (
		tool: FibToolType,
		widthMultiplier: number | null,
		extendLines?: boolean
	) => {
		if (this.isRewound || !this.securityId) return;
		const currentTools = this.userPreferences?.fibonacci_tools?.[this.securityId];
		let updatedSecurityTools: SecurityFibonacciTools;
		if (tool === 'retracement') {
			const currentDrawing = currentTools?.retracement;
			updatedSecurityTools = {
				...currentTools,
				retracement: currentDrawing
					? { ...currentDrawing, widthMultiplier, extendLines: Boolean(extendLines) }
					: null
			};
		} else {
			const currentDrawing = currentTools?.extension;
			updatedSecurityTools = {
				...currentTools,
				extension: currentDrawing
					? { ...currentDrawing, widthMultiplier, extendLines: Boolean(extendLines) }
					: null
			};
		}
		const updatedAllTools = updateSecurityFibonacciTools(
			this.userPreferences?.fibonacci_tools,
			this.securityId,
			updatedSecurityTools
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			fibonacci_tools: updatedAllTools
		};
		this.recordDrawingStateChange();
		try {
			await this._userPreferencesService.patchPreferences({
				fibonacci_tools: updatedAllTools
			});
		} catch (err) {
			console.error('Failed to persist fibonacci tools preference:', err);
		}
		this.options.onPreferencesChanged?.(this.userPreferences);
	};

	handleDrawingChange = async <K extends keyof SecurityDrawings>(
		toolKey: K,
		items: NonNullable<SecurityDrawings[K]>
	) => {
		if (this.isRewound || !this.securityId) return;
		const updatedAllDrawings = updateSecurityDrawings(
			this.userPreferences?.drawings,
			this.securityId,
			toolKey,
			items
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			drawings: updatedAllDrawings
		};
		this.recordDrawingStateChange({ coalesce: this.isDraggingDrawing });
		if (this.isDraggingDrawing) {
			this._pendingDrawingPreferences = {
				...(this._pendingDrawingPreferences ?? {}),
				drawings: updatedAllDrawings
			};
			this.options.onPreferencesChanged?.(this.userPreferences);
			return;
		}
		try {
			await this._userPreferencesService.patchPreferences({
				drawings: updatedAllDrawings
			});
		} catch (err) {
			console.error(`Failed to persist ${String(toolKey)} drawings preference:`, err);
		}
		this.options.onPreferencesChanged?.(this.userPreferences);
	};

	handleRemoveDrawing = async <K extends keyof SecurityDrawings>(toolKey: K, id: string) => {
		if (this.isRewound) return;
		if (toolKey === 'measures' && this.selectedMeasureId === id) {
			this.selectedMeasureId = null;
		} else if (toolKey === 'horizontalLines' && this.selectedHorizontalLineId === id) {
			this.selectedHorizontalLineId = null;
		} else if (toolKey === 'lines' && this.selectedLineId === id) {
			this.selectedLineId = null;
		}
		if (!this.securityId) return;
		const updatedAllDrawings = removeSecurityDrawings(
			this.userPreferences?.drawings,
			this.securityId,
			toolKey,
			id
		);
		this.userPreferences = {
			...(this.userPreferences ?? {}),
			drawings: updatedAllDrawings
		};
		this.recordDrawingStateChange();
		try {
			await this._userPreferencesService.patchPreferences({
				drawings: updatedAllDrawings
			});
		} catch (err) {
			console.error(`Failed to persist ${String(toolKey)} drawings preference:`, err);
		}
		this.options.onPreferencesChanged?.(this.userPreferences);
	};

	handleMeasureChange = (measures: MeasureDrawing[]) => {
		return this.handleDrawingChange('measures', measures);
	};

	handleRemoveMeasure = (measureId: string) => {
		return this.handleRemoveDrawing('measures', measureId);
	};

	handleHorizontalLineChange = (lines: HorizontalLineDrawing[]) => {
		return this.handleDrawingChange('horizontalLines', lines);
	};

	handleRemoveHorizontalLine = (lineId: string) => {
		return this.handleRemoveDrawing('horizontalLines', lineId);
	};

	handleLineChange = (lines: LineDrawing[]) => {
		return this.handleDrawingChange('lines', lines);
	};

	handleRemoveLine = (lineId: string) => {
		return this.handleRemoveDrawing('lines', lineId);
	};

	showSaveFeedback = () => {
		if (this._saveFeedbackTimer) {
			clearTimeout(this._saveFeedbackTimer);
		}
		this.saveFeedback = 'saved';
		this._saveFeedbackTimer = setTimeout(() => {
			this.saveFeedback = 'idle';
			this._saveFeedbackTimer = null;
		}, 1500);
	};

	loadSnapshots = async () => {
		if (!this.securityId) return;
		try {
			const res = await this._snapshotsService.getSnapshots(this.securityId);
			this.snapshots = res.sort((a, b) => Date.parse(a.captured_at) - Date.parse(b.captured_at));
			if (this.snapshots.length > 0) {
				this.isTimelineVisible = true;
			}
		} catch (err) {
			console.error('Failed to load snapshots:', err);
		}
	};

	handleSaveSnapshot = async (candles?: Candle[]) => {
		if (this.isRewound) return;
		if (!this.securityId) return;
		const candleList = candles ?? this.displayCandles;
		if (!candleList.length) return;

		const drawings: RewindDrawings = {
			elliott_waves: this.securityElliottWaves,
			fibonacci_tools: this.securityFibonacciTools,
			drawings: this.securityDrawings
		};

		const hasWavePoints = Boolean(
			drawings.elliott_waves?.waves?.some((w) => w.points && w.points.length > 0)
		);
		const hasFibTools = Boolean(
			drawings.fibonacci_tools?.retracement || drawings.fibonacci_tools?.extension
		);
		const hasNewDrawings = !isSecurityDrawingsEmpty(drawings.drawings);

		if (!hasWavePoints && !hasFibTools && !hasNewDrawings) {
			return;
		}

		const dataWindow: RewindDataWindow = {
			first: normalizeCandleTime(candleList[0].time),
			last: normalizeCandleTime(candleList[candleList.length - 1].time)
		};

		const snapshot = captureSnapshot(drawings, dataWindow);

		const last = this.snapshots[this.snapshots.length - 1];
		if (last && areSnapshotsEqual(snapshot, last)) {
			this.showSaveFeedback();
			this._toast.info('Chart snapshot already up to date');
			return;
		}

		try {
			const created = await this._snapshotsService.createSnapshot(this.securityId, {
				drawings,
				data_window: dataWindow,
				captured_at: snapshot.captured_at
			});
			this.snapshots = [...this.snapshots, created];
			this.isTimelineVisible = true;
			this.showSaveFeedback();
			this._toast.success('Chart snapshot saved');
		} catch (err) {
			console.error('Failed to persist rewind snapshot:', err);
			this._toast.error('Failed to save chart snapshot');
		}
	};

	handleKeyDown = (event: KeyboardEvent, chartRef?: ChartInstance | null) => {
		const target = event.target as HTMLElement | null;
		if (
			target &&
			typeof target.closest === 'function' &&
			(target.tagName === 'INPUT' ||
				target.tagName === 'TEXTAREA' ||
				target.isContentEditable ||
				target.closest('input, textarea, [contenteditable="true"]'))
		) {
			return;
		}

		const ref = chartRef ?? this.options.getChartRef?.();

		if (event.key === 'Delete' || event.key === 'Backspace') {
			if (this.isRewound) return;
			const selectedWaveId = ref?.getSelectedWaveId?.();
			const waveDegree = this.selectedWaveDegree ?? ref?.getSelectedWaveDegree?.();
			const fibTool = this.selectedFibTool ?? ref?.getSelectedFibTool?.();
			const measureId = this.selectedMeasureId ?? ref?.getSelectedMeasureId?.();
			const horizontalLineId =
				this.selectedHorizontalLineId ?? ref?.getSelectedHorizontalLineId?.();
			const lineId = this.selectedLineId ?? ref?.getSelectedLineId?.();

			if (waveDegree || selectedWaveId) {
				event.preventDefault();
				const degreeToClear = waveDegree ?? undefined;
				this.selectedWaveDegree = null;
				void this.handleClearWave(degreeToClear, ref);
			} else if (fibTool) {
				event.preventDefault();
				this.selectedFibTool = null;
				void this.handleClearFib(fibTool);
			} else if (measureId) {
				event.preventDefault();
				this.selectedMeasureId = null;
				void this.handleRemoveMeasure(measureId);
			} else if (horizontalLineId) {
				event.preventDefault();
				this.selectedHorizontalLineId = null;
				void this.handleRemoveHorizontalLine(horizontalLineId);
			} else if (lineId) {
				event.preventDefault();
				this.selectedLineId = null;
				void this.handleRemoveLine(lineId);
			}
		} else if (event.key === 'Escape') {
			this.cancelActiveDrawing();
		} else if ((event.metaKey || event.ctrlKey) && (event.key === 'z' || event.key === 'Z')) {
			event.preventDefault();
			if (this.isRewound) return;
			if (event.shiftKey) {
				void this.handleRedo();
			} else {
				void this.handleUndo();
			}
		} else if ((event.metaKey || event.ctrlKey) && (event.key === 'y' || event.key === 'Y')) {
			event.preventDefault();
			if (this.isRewound) return;
			void this.handleRedo();
		} else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
			event.preventDefault();
			if (this.isRewound) return;
			void this.handleSaveSnapshot();
		} else if ((event.metaKey || event.ctrlKey) && event.key === ',') {
			if (this.options.onChartSettingsOpen) {
				event.preventDefault();
				this.options.onChartSettingsOpen();
			}
		}
	};

	destroy = () => {
		if (this._saveFeedbackTimer) {
			clearTimeout(this._saveFeedbackTimer);
			this._saveFeedbackTimer = null;
		}
		if (this._unsubscribeHistory) {
			this._unsubscribeHistory();
			this._unsubscribeHistory = null;
		}
	};
}

const CHART_DRAWINGS_SERVICE_KEY = Symbol('chart-drawings-service');

export function setChartDrawingsService(service?: ChartDrawingsService): ChartDrawingsService {
	const instance = service ?? new ChartDrawingsService();
	setContext(CHART_DRAWINGS_SERVICE_KEY, instance);
	return instance;
}

export function getChartDrawingsService(): ChartDrawingsService | undefined {
	try {
		return getContext<ChartDrawingsService>(CHART_DRAWINGS_SERVICE_KEY);
	} catch {
		return undefined;
	}
}
