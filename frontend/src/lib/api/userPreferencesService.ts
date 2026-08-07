import { ApiClient } from './apiClient';
import type { IndicatorConfig } from './indicatorsService';

export type ChartStyle = 'heikin_ashi' | 'candlestick';

export interface UserPreferences {
	timeframe?: string | null;
	chart_style?: ChartStyle | null;
	indicators?: Record<string, IndicatorConfig> | null;
}

export class UserPreferencesService extends ApiClient {
	async getPreferences(): Promise<UserPreferences> {
		return await this.get<UserPreferences>('/accounts/me/preferences');
	}

	async savePreferences(prefs: UserPreferences): Promise<UserPreferences> {
		return await this.put<UserPreferences, UserPreferences>('/accounts/me/preferences', prefs);
	}
}

export const getUserPreferencesService = (customFetch?: typeof fetch) =>
	new UserPreferencesService(customFetch);
export const userPreferencesService = getUserPreferencesService();
