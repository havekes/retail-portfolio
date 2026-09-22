import { ApiClient } from './apiClient';
import type { IndicatorConfig } from './indicatorsService';
import type { HoldingsTableConfig } from '$lib/components/holdings/holdings-table-columns';
import type { HoldingsGroupMode } from '$lib/utils/finance/holdings-group';
import type {
	DegreeWaveCount,
	SecurityElliottWaves,
	TargetWave,
	WaveDegree,
	WavePoint,
	WaveAlertPercents,
	WaveSettings
} from '$lib/utils/finance/elliott-wave';
import type {
	FibPoint,
	FibLevelConfig,
	FibRetracementDrawing,
	FibExtensionDrawing,
	SecurityFibonacciTools,
	FibonacciPreferences,
	FibComputedLevel,
	FibToolType
} from '$lib/utils/finance/fibonacci';
import type {
	DrawingPoint,
	MeasureDrawing,
	HorizontalLineDrawing,
	LineDrawing,
	Drawing,
	DrawingToolType,
	SecurityDrawings,
	SecurityDrawingsMap
} from '$lib/utils/finance/drawings';

export type ChartStyle = 'heikin_ashi' | 'candlestick';

export type {
	DegreeWaveCount,
	SecurityElliottWaves,
	TargetWave,
	WaveDegree,
	WavePoint,
	WaveAlertPercents,
	WaveSettings,
	FibPoint,
	FibLevelConfig,
	FibRetracementDrawing,
	FibExtensionDrawing,
	SecurityFibonacciTools,
	FibonacciPreferences,
	FibComputedLevel,
	FibToolType,
	DrawingPoint,
	MeasureDrawing,
	HorizontalLineDrawing,
	LineDrawing,
	Drawing,
	DrawingToolType,
	SecurityDrawings,
	SecurityDrawingsMap
};

export interface UserPreferences {
	timeframe?: string | null;
	chart_style?: ChartStyle | null;
	indicators?: Record<string, IndicatorConfig> | null;
	sidebar_open?: boolean | null;
	sidebar_watchlists?: boolean | null;
	collapsed_watchlist_ids?: string[] | null;
	holdings_period?: string | null;
	elliott_waves?: Record<string, SecurityElliottWaves> | null;
	fibonacci_tools?: Record<string, SecurityFibonacciTools> | null;
	drawings?: Record<string, SecurityDrawings> | null;
	wave_settings?: WaveSettings | null;
	chart_hide_labels?: boolean | null;
	watchlist_order?: string[] | null;
	holdings_table?: HoldingsTableConfig | null;
	holdings_group?: HoldingsGroupMode | null;
	indicator_pane_heights?: Record<string, number> | null;
}

export class UserPreferencesService extends ApiClient {
	async getPreferences(tokenOverride?: string | null): Promise<UserPreferences> {
		return await this.get<UserPreferences>('/accounts/me/preferences', undefined, tokenOverride);
	}

	async savePreferences(
		prefs: UserPreferences,
		tokenOverride?: string | null
	): Promise<UserPreferences> {
		return await this.put<UserPreferences, UserPreferences>(
			'/accounts/me/preferences',
			prefs,
			undefined,
			tokenOverride
		);
	}

	async patchPreferences(
		prefs: Partial<UserPreferences>,
		tokenOverride?: string | null
	): Promise<UserPreferences> {
		return await this.patch<UserPreferences, Partial<UserPreferences>>(
			'/accounts/me/preferences',
			prefs,
			undefined,
			tokenOverride
		);
	}
}

export const getUserPreferencesService = (customFetch?: typeof fetch) =>
	new UserPreferencesService(customFetch);
export const userPreferencesService = getUserPreferencesService();
