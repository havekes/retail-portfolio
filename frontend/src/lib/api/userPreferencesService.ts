import { ApiClient } from './apiClient';
import type { IndicatorConfig } from './indicatorsService';

export type ChartStyle = 'heikin_ashi' | 'candlestick';

export interface UserPreferences {
	timeframe?: string | null;
	chart_style?: ChartStyle | null;
	indicators?: Record<string, IndicatorConfig> | null;
	sidebar_open?: boolean | null;
	holdings_period?: string | null;
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
