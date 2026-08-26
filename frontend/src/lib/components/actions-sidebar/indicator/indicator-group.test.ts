import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/svelte';
import IndicatorGroup from './indicator-group.svelte';
import { createIndicatorConfigs } from '$lib/chart/indicator-defaults';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		getPreferences: vi.fn(),
		patchPreferences: vi.fn()
	}
}));

import { userPreferencesService } from '$lib/api/userPreferencesService';

describe('IndicatorGroup Component', () => {
	const mockOnIndicatorConfigChange = vi.fn();
	const mockOnIndicatorToggle = vi.fn();
	const mockOnPreferencesLoaded = vi.fn();

	// Default-derived page state; rsi stays disabled here, mirroring the stale
	// page `indicatorConfigs` that is NOT updated when the sidebar toggle flips.
	const indicatorConfigs = createIndicatorConfigs();

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: {
				rsi: { enabled: true, color: '#111111', settings: { period: 21 } }
			}
		});
		vi.mocked(userPreferencesService.patchPreferences).mockResolvedValue({});
	});

	function renderGroup() {
		return render(IndicatorGroup, {
			props: {
				expanded: true,
				indicatorConfigs,
				onIndicatorConfigChange: mockOnIndicatorConfigChange,
				onIndicatorToggle: mockOnIndicatorToggle,
				onPreferencesLoaded: mockOnPreferencesLoaded
			}
		});
	}

	async function openRsiSettings() {
		const rsiRow = screen.getByText('RSI').closest('[role="button"]');
		expect(rsiRow).not.toBeNull();
		const gearButton = within(rsiRow as HTMLElement).getByRole('button', { name: /settings/i });
		await fireEvent.click(gearButton);
		await waitFor(() => expect(screen.getByText('RSI Settings')).toBeInTheDocument());
	}

	it('renders the reset button in the indicator settings modal', async () => {
		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		await openRsiSettings();

		expect(screen.getByTestId('reset-indicator-btn')).toBeInTheDocument();
	});

	it('restores defaults, preserves enabled, persists, and re-renders an enabled indicator', async () => {
		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		await openRsiSettings();
		await fireEvent.click(screen.getByTestId('reset-indicator-btn'));

		// Persisted preference wins over the stale page indicatorConfigs (rsi
		// enabled: false there) — the chart must re-render with restored settings.
		expect(mockOnIndicatorConfigChange).toHaveBeenCalledWith(
			'rsi',
			expect.objectContaining({ color: '#06b6d4', period: 14 }),
			true
		);

		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					rsi: { enabled: true, color: '#06b6d4', settings: { period: 14 } }
				}
			});
		});
	});

	it('does not request a chart re-render when the indicator is disabled in preferences', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: {
				rsi: { enabled: false, color: '#111111', settings: { period: 21 } }
			}
		});

		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		await openRsiSettings();
		await fireEvent.click(screen.getByTestId('reset-indicator-btn'));

		expect(mockOnIndicatorConfigChange).toHaveBeenCalledWith(
			'rsi',
			expect.objectContaining({ color: '#06b6d4', period: 14 }),
			false
		);

		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					rsi: { enabled: false, color: '#06b6d4', settings: { period: 14 } }
				}
			});
		});
	});

	it('restores macd fast/slow/signal defaults and keeps enabled from preferences', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: {
				macd: {
					enabled: true,
					color: '#000000',
					settings: { fast: 5, slow: 10, signal: 3 }
				}
			}
		});

		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		const macdRow = screen.getByText('MACD').closest('[role="button"]');
		expect(macdRow).not.toBeNull();
		await fireEvent.click(
			within(macdRow as HTMLElement).getByRole('button', { name: /settings/i })
		);
		await waitFor(() => expect(screen.getByText('MACD Settings')).toBeInTheDocument());

		await fireEvent.click(screen.getByTestId('reset-indicator-btn'));

		expect(mockOnIndicatorConfigChange).toHaveBeenCalledWith(
			'macd',
			expect.objectContaining({ color: '#ef4444', fast: 12, slow: 26, signal: 9 }),
			true
		);

		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					macd: {
						enabled: true,
						color: '#ef4444',
						// macd's default period is 0 and is promoted into settings,
						// consistent with the existing save path (harmless).
						settings: { fast: 12, slow: 26, signal: 9, period: 0 }
					}
				}
			});
		});
	});

	it('restores Bollinger Bands color/period/stdDev defaults and keeps enabled from preferences', async () => {
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: {
				bb: { enabled: true, color: '#111111', settings: { period: 10, stdDev: 3 } }
			}
		});

		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		const bbRow = screen.getByText('Bollinger Bands').closest('[role="button"]');
		expect(bbRow).not.toBeNull();
		await fireEvent.click(within(bbRow as HTMLElement).getByRole('button', { name: /settings/i }));
		await waitFor(() => expect(screen.getByText('Bollinger Bands Settings')).toBeInTheDocument());

		await fireEvent.click(screen.getByTestId('reset-indicator-btn'));

		expect(mockOnIndicatorConfigChange).toHaveBeenCalledWith(
			'bb',
			expect.objectContaining({ color: '#8b5cf6', period: 20, stdDev: 2 }),
			true
		);

		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					bb: { enabled: true, color: '#8b5cf6', settings: { period: 20, stdDev: 2 } }
				}
			});
		});
	});

	it('does not clobber a sidebar-toggle enabled flag when saving settings', async () => {
		// bb starts disabled in preferences, mirroring the stale page
		// indicatorConfigs (bb.enabled === false from defaults).
		vi.mocked(userPreferencesService.getPreferences).mockResolvedValue({
			indicators: {
				bb: { enabled: false, color: '#111111', settings: { period: 10, stdDev: 3 } }
			}
		});

		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		// Toggle bb on by clicking the row wrapper (not the gear). This flips
		// the live preference to enabled: true, but the page indicatorConfigs
		// (and therefore the modal-bound config) stays stale at false.
		const bbRow = screen.getByText('Bollinger Bands').closest('[role="button"]');
		expect(bbRow).not.toBeNull();
		await fireEvent.click(bbRow as HTMLElement);
		await waitFor(() =>
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					bb: { enabled: true, color: '#111111', settings: { period: 10, stdDev: 3 } }
				}
			})
		);

		// Clear the toggle patch so the Save assertion only sees the save call.
		vi.mocked(userPreferencesService.patchPreferences).mockClear();

		// Open bb settings (modal-bound config reads stale page state, enabled
		// false) and Save.
		await fireEvent.click(within(bbRow as HTMLElement).getByRole('button', { name: /settings/i }));
		await waitFor(() => expect(screen.getByText('Bollinger Bands Settings')).toBeInTheDocument());
		await fireEvent.click(screen.getByText('Save settings'));

		// The saved entry must keep enabled: true (from live preferences), not
		// be clobbered back to the stale modal config's false.
		await waitFor(() => {
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				indicators: {
					bb: { enabled: true, color: '#8b5cf6', settings: { period: 20, stdDev: 2 } }
				}
			});
		});
	});

	it('displays Info icon button for MACD, BB, RSI, OBV, and opens the educational help modal', async () => {
		renderGroup();
		await waitFor(() => expect(userPreferencesService.getPreferences).toHaveBeenCalled());

		// Verify Info buttons exist for macd, bb, rsi, obv
		expect(screen.getByTestId('help-macd-btn')).toBeInTheDocument();
		expect(screen.getByTestId('help-bb-btn')).toBeInTheDocument();
		expect(screen.getByTestId('help-rsi-btn')).toBeInTheDocument();
		expect(screen.getByTestId('help-obv-btn')).toBeInTheDocument();

		// Verify Info buttons do not exist for other indicators (e.g., volume, avgPrice, ma50)
		expect(screen.queryByTestId('help-volume-btn')).toBeNull();
		expect(screen.queryByTestId('help-avgPrice-btn')).toBeNull();
		expect(screen.queryByTestId('help-ma50-btn')).toBeNull();

		// Click MACD info button and verify educational modal opens with MACD content
		await fireEvent.click(screen.getByTestId('help-macd-btn'));
		await waitFor(() => {
			expect(screen.getByText('Moving Average Convergence Divergence (MACD)')).toBeInTheDocument();
		});

		// Close modal
		await fireEvent.click(screen.getByTestId('help-modal-close-btn'));

		// Click RSI info button and verify educational modal opens with RSI content
		await fireEvent.click(screen.getByTestId('help-rsi-btn'));
		await waitFor(() => {
			expect(screen.getByText('Relative Strength Index (RSI)')).toBeInTheDocument();
		});
	});
});
