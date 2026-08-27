import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import ChartSettingsModal from './chart-settings-modal.svelte';
import type { WaveSettings } from '$lib/utils/finance/elliott-wave';
import {
	DEFAULT_FIB_RETRACEMENT_LEVELS,
	DEFAULT_FIB_EXTENSION_LEVELS,
	type FibLevelConfig,
	type FibToolType
} from '$lib/utils/finance/fibonacci';

describe('ChartSettingsModal Component', () => {
	let mockOnSaveChartHideLabels = vi.fn<(hide: boolean) => void>();
	let mockOnSaveWaveSettings = vi.fn<(settings: WaveSettings) => void>();
	let mockOnFibLevelsChange = vi.fn<(tool: FibToolType, levels: FibLevelConfig[]) => void>();
	let mockOnClose = vi.fn<() => void>();

	beforeEach(() => {
		vi.clearAllMocks();
		mockOnSaveChartHideLabels = vi.fn<(hide: boolean) => void>();
		mockOnSaveWaveSettings = vi.fn<(settings: WaveSettings) => void>();
		mockOnFibLevelsChange = vi.fn<(tool: FibToolType, levels: FibLevelConfig[]) => void>();
		mockOnClose = vi.fn<() => void>();
	});

	describe('Rendering & Dialog Visibility', () => {
		it('does not render dialog content when open is false', () => {
			render(ChartSettingsModal, {
				props: {
					open: false
				}
			});

			expect(screen.queryByText('Chart Settings')).not.toBeInTheDocument();
		});

		it('renders dialog header, top-level tabs, and General panel by default when open', () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					onSaveChartHideLabels: mockOnSaveChartHideLabels,
					onClose: mockOnClose
				}
			});

			expect(screen.getByText('Chart Settings')).toBeInTheDocument();
			expect(
				screen.getByText('Configure Elliott Wave alerts, snapping, and Fibonacci tool levels.')
			).toBeInTheDocument();

			// Top-level tab selector buttons
			const generalTab = screen.getByRole('tab', { name: 'General' });
			const wavesTab = screen.getByRole('tab', { name: 'Waves' });
			const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });
			expect(generalTab).toBeInTheDocument();
			expect(wavesTab).toBeInTheDocument();
			expect(fibTab).toBeInTheDocument();
			expect(generalTab).toHaveAttribute('aria-selected', 'true');
			expect(wavesTab).toHaveAttribute('aria-selected', 'false');
			expect(fibTab).toHaveAttribute('aria-selected', 'false');

			// General panel elements
			expect(screen.getByTestId('general-settings-panel')).toBeInTheDocument();
			expect(screen.getByTestId('hide-labels-checkbox')).toBeInTheDocument();
			expect(screen.getByTestId('cancel-general-btn')).toBeInTheDocument();
			expect(screen.getByTestId('save-general-btn')).toBeInTheDocument();
		});

		it('opens with Waves panel selected when initialSection is "waves"', () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					onSaveWaveSettings: mockOnSaveWaveSettings,
					onClose: mockOnClose
				}
			});

			const generalTab = screen.getByRole('tab', { name: 'General' });
			const wavesTab = screen.getByRole('tab', { name: 'Waves' });
			const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });
			expect(generalTab).toHaveAttribute('aria-selected', 'false');
			expect(wavesTab).toHaveAttribute('aria-selected', 'true');
			expect(fibTab).toHaveAttribute('aria-selected', 'false');

			// Waves panel elements
			expect(screen.getByTestId('waves-settings-panel')).toBeInTheDocument();
			expect(screen.getByTestId('snap-to-wicks-checkbox')).toBeInTheDocument();
			expect(screen.getByTestId('cycle-wave3-input')).toBeInTheDocument();
			expect(screen.getByTestId('cycle-wave5-input')).toBeInTheDocument();
			expect(screen.getByTestId('primary-wave3-input')).toBeInTheDocument();
			expect(screen.getByTestId('primary-wave5-input')).toBeInTheDocument();
		});

		it('opens with Fibonacci panel selected when initialSection is "fibonacci"', () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const generalTab = screen.getByRole('tab', { name: 'General' });
			const wavesTab = screen.getByRole('tab', { name: 'Waves' });
			const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });
			expect(generalTab).toHaveAttribute('aria-selected', 'false');
			expect(wavesTab).toHaveAttribute('aria-selected', 'false');
			expect(fibTab).toHaveAttribute('aria-selected', 'true');

			expect(screen.getByTestId('fibonacci-settings-panel')).toBeInTheDocument();
		});

		it('switches between General, Waves, and Fibonacci sections on tab click', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					onSaveChartHideLabels: mockOnSaveChartHideLabels,
					onSaveWaveSettings: mockOnSaveWaveSettings,
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const generalTab = screen.getByRole('tab', { name: 'General' });
			const wavesTab = screen.getByRole('tab', { name: 'Waves' });
			const fibTab = screen.getByRole('tab', { name: 'Fibonacci' });

			// Initially General
			expect(generalTab).toHaveAttribute('aria-selected', 'true');
			expect(screen.getByTestId('general-settings-panel')).toBeInTheDocument();
			expect(screen.queryByTestId('waves-settings-panel')).not.toBeInTheDocument();
			expect(screen.queryByTestId('fibonacci-settings-panel')).not.toBeInTheDocument();

			// Switch to Waves
			await fireEvent.click(wavesTab);
			expect(wavesTab).toHaveAttribute('aria-selected', 'true');
			expect(generalTab).toHaveAttribute('aria-selected', 'false');
			expect(screen.getByTestId('waves-settings-panel')).toBeInTheDocument();
			expect(screen.queryByTestId('general-settings-panel')).not.toBeInTheDocument();

			// Switch to Fibonacci
			await fireEvent.click(fibTab);
			expect(fibTab).toHaveAttribute('aria-selected', 'true');
			expect(wavesTab).toHaveAttribute('aria-selected', 'false');
			expect(screen.getByTestId('fibonacci-settings-panel')).toBeInTheDocument();
			expect(screen.queryByTestId('waves-settings-panel')).not.toBeInTheDocument();

			// Switch back to General
			await fireEvent.click(generalTab);
			expect(generalTab).toHaveAttribute('aria-selected', 'true');
			expect(fibTab).toHaveAttribute('aria-selected', 'false');
			expect(screen.getByTestId('general-settings-panel')).toBeInTheDocument();
		});
	});

	describe('General Section - Initial Values, Toggling, and Actions', () => {
		it('populates initial checkbox state from chartHideLabels prop', () => {
			const { rerender } = render(ChartSettingsModal, {
				props: {
					open: true,
					chartHideLabels: true
				}
			});

			expect(screen.getByTestId('hide-labels-checkbox')).toHaveAttribute('aria-checked', 'true');

			rerender({ open: true, chartHideLabels: false });
			expect(screen.getByTestId('hide-labels-checkbox')).toHaveAttribute('aria-checked', 'false');
		});

		it('defaults chartHideLabels to unchecked when not provided', () => {
			render(ChartSettingsModal, {
				props: {
					open: true
				}
			});

			expect(screen.getByTestId('hide-labels-checkbox')).toHaveAttribute('aria-checked', 'false');
		});

		it('toggles hide labels checkbox and saves updated value', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					chartHideLabels: false,
					onSaveChartHideLabels: mockOnSaveChartHideLabels,
					onClose: mockOnClose
				}
			});

			const checkbox = screen.getByTestId('hide-labels-checkbox');
			await fireEvent.click(checkbox);

			const saveBtn = screen.getByTestId('save-general-btn');
			await fireEvent.click(saveBtn);

			expect(mockOnSaveChartHideLabels).toHaveBeenCalledTimes(1);
			expect(mockOnSaveChartHideLabels).toHaveBeenCalledWith(true);
			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});

		it('discards unsaved changes and invokes onClose when Cancel button is clicked', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					chartHideLabels: false,
					onSaveChartHideLabels: mockOnSaveChartHideLabels,
					onClose: mockOnClose
				}
			});

			const checkbox = screen.getByTestId('hide-labels-checkbox');
			await fireEvent.click(checkbox);

			const cancelBtn = screen.getByTestId('cancel-general-btn');
			await fireEvent.click(cancelBtn);

			expect(mockOnSaveChartHideLabels).not.toHaveBeenCalled();
			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});
	});

	describe('Waves Section - Initial Values & State Population', () => {
		it('populates initial form fields from waveSettings prop', () => {
			const initialSettings: WaveSettings = {
				snap_to_wicks: true,
				alert_percents: {
					cycle: { wave3: 85, wave5: 92.5 },
					primary: { wave3: 75, wave5: null }
				}
			};

			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: initialSettings,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const snapCheckbox = screen.getByTestId('snap-to-wicks-checkbox');
			const cycle3Input = screen.getByTestId('cycle-wave3-input') as HTMLInputElement;
			const cycle5Input = screen.getByTestId('cycle-wave5-input') as HTMLInputElement;
			const primary3Input = screen.getByTestId('primary-wave3-input') as HTMLInputElement;
			const primary5Input = screen.getByTestId('primary-wave5-input') as HTMLInputElement;

			expect(snapCheckbox).toHaveAttribute('aria-checked', 'true');
			expect(cycle3Input.value).toBe('85');
			expect(cycle5Input.value).toBe('92.5');
			expect(primary3Input.value).toBe('75');
			expect(primary5Input.value).toBe('');
		});

		it('populates blank/default form fields when waveSettings is null or undefined', () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: null,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const snapCheckbox = screen.getByTestId('snap-to-wicks-checkbox');
			const cycle3Input = screen.getByTestId('cycle-wave3-input') as HTMLInputElement;
			const cycle5Input = screen.getByTestId('cycle-wave5-input') as HTMLInputElement;
			const primary3Input = screen.getByTestId('primary-wave3-input') as HTMLInputElement;
			const primary5Input = screen.getByTestId('primary-wave5-input') as HTMLInputElement;

			expect(snapCheckbox).toHaveAttribute('aria-checked', 'false');
			expect(cycle3Input.value).toBe('');
			expect(cycle5Input.value).toBe('');
			expect(primary3Input.value).toBe('');
			expect(primary5Input.value).toBe('');
		});
	});

	describe('Waves Section - Editing, Validation, and Actions', () => {
		it('toggles snap_to_wicks and saves updated value', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: { snap_to_wicks: false },
					onSaveWaveSettings: mockOnSaveWaveSettings,
					onClose: mockOnClose
				}
			});

			const snapCheckbox = screen.getByTestId('snap-to-wicks-checkbox');
			await fireEvent.click(snapCheckbox);

			const saveBtn = screen.getByTestId('save-waves-btn');
			await fireEvent.click(saveBtn);

			expect(mockOnSaveWaveSettings).toHaveBeenCalledTimes(1);
			expect(mockOnSaveWaveSettings).toHaveBeenCalledWith({
				snap_to_wicks: true,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			});
			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});

		it('allows entering numeric percentages and saves normalized WaveSettings object', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: null,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const cycle3Input = screen.getByTestId('cycle-wave3-input');
			const cycle5Input = screen.getByTestId('cycle-wave5-input');
			const primary3Input = screen.getByTestId('primary-wave3-input');
			const primary5Input = screen.getByTestId('primary-wave5-input');

			await fireEvent.input(cycle3Input, { target: { value: '90' } });
			await fireEvent.input(cycle5Input, { target: { value: '95.5' } });
			await fireEvent.input(primary3Input, { target: { value: '80' } });
			await fireEvent.input(primary5Input, { target: { value: '88' } });

			const saveBtn = screen.getByTestId('save-waves-btn');
			await fireEvent.click(saveBtn);

			expect(mockOnSaveWaveSettings).toHaveBeenCalledTimes(1);
			expect(mockOnSaveWaveSettings).toHaveBeenCalledWith({
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: 90, wave5: 95.5 },
					primary: { wave3: 80, wave5: 88 }
				}
			});
		});

		it('normalizes empty strings to null for partial alert percent configurations', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: null,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const cycle3Input = screen.getByTestId('cycle-wave3-input');
			await fireEvent.input(cycle3Input, { target: { value: '75' } });

			const saveBtn = screen.getByTestId('save-waves-btn');
			await fireEvent.click(saveBtn);

			expect(mockOnSaveWaveSettings).toHaveBeenCalledWith({
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: 75, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			});
		});

		it('shows validation error and disables Save button on negative percent input', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: null,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const cycle3Input = screen.getByTestId('cycle-wave3-input');
			await fireEvent.input(cycle3Input, { target: { value: '-10' } });

			const errorBanner = screen.getByTestId('waves-validation-error');
			expect(errorBanner).toBeInTheDocument();
			expect(errorBanner).toHaveTextContent('Percentages cannot be negative.');

			const saveBtn = screen.getByTestId('save-waves-btn');
			expect(saveBtn).toBeDisabled();

			await fireEvent.click(saveBtn);
			expect(mockOnSaveWaveSettings).not.toHaveBeenCalled();
		});

		it('resets all wave settings to defaults on "Reset to Defaults" click', async () => {
			const initialSettings: WaveSettings = {
				snap_to_wicks: true,
				alert_percents: {
					cycle: { wave3: 90, wave5: 90 },
					primary: { wave3: 80, wave5: 80 }
				}
			};

			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: initialSettings,
					onSaveWaveSettings: mockOnSaveWaveSettings
				}
			});

			const resetBtn = screen.getByTestId('reset-waves-btn');
			await fireEvent.click(resetBtn);

			const snapCheckbox = screen.getByTestId('snap-to-wicks-checkbox');
			const cycle3Input = screen.getByTestId('cycle-wave3-input') as HTMLInputElement;
			const cycle5Input = screen.getByTestId('cycle-wave5-input') as HTMLInputElement;
			const primary3Input = screen.getByTestId('primary-wave3-input') as HTMLInputElement;
			const primary5Input = screen.getByTestId('primary-wave5-input') as HTMLInputElement;

			expect(snapCheckbox).toHaveAttribute('aria-checked', 'false');
			expect(cycle3Input.value).toBe('');
			expect(cycle5Input.value).toBe('');
			expect(primary3Input.value).toBe('');
			expect(primary5Input.value).toBe('');

			// Saving after reset persists empty/null defaults
			const saveBtn = screen.getByTestId('save-waves-btn');
			await fireEvent.click(saveBtn);

			expect(mockOnSaveWaveSettings).toHaveBeenCalledWith({
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: null, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			});
		});

		it('discards unsaved changes and invokes onClose when Cancel button is clicked', async () => {
			const initialSettings: WaveSettings = {
				snap_to_wicks: false,
				alert_percents: {
					cycle: { wave3: 50, wave5: null },
					primary: { wave3: null, wave5: null }
				}
			};

			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'waves',
					waveSettings: initialSettings,
					onSaveWaveSettings: mockOnSaveWaveSettings,
					onClose: mockOnClose
				}
			});

			const cycle3Input = screen.getByTestId('cycle-wave3-input');
			await fireEvent.input(cycle3Input, { target: { value: '999' } });

			const cancelBtn = screen.getByTestId('cancel-waves-btn');
			await fireEvent.click(cancelBtn);

			expect(mockOnSaveWaveSettings).not.toHaveBeenCalled();
			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});
	});

	describe('Fibonacci Section - Migrated Dialog Tests', () => {
		it('renders Fibonacci tool tab switcher and retracement levels by default', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange,
					onClose: mockOnClose
				}
			});

			const retracementTab = screen.getByRole('tab', { name: 'Retracement' });
			const extensionTab = screen.getByRole('tab', { name: 'Extension' });
			expect(retracementTab).toBeInTheDocument();
			expect(extensionTab).toBeInTheDocument();
			expect(retracementTab).toHaveAttribute('aria-selected', 'true');
			expect(extensionTab).toHaveAttribute('aria-selected', 'false');

			// Standard Retracement levels (0.0 to 1.618)
			for (const level of DEFAULT_FIB_RETRACEMENT_LEVELS) {
				const expectedPercent = `${(level.ratio * 100).toFixed(1)}%`;
				expect(screen.getByTestId(`fib-level-row-${level.ratio}`)).toBeInTheDocument();
				expect(screen.getByText(expectedPercent)).toBeInTheDocument();
			}

			const colorBadges = screen.getAllByTestId('fib-level-color-badge');
			expect(colorBadges.length).toBe(DEFAULT_FIB_RETRACEMENT_LEVELS.length);
		});

		it('opens with Extension tab selected when activeTool is "extension"', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					activeTool: 'extension',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const retracementTab = screen.getByRole('tab', { name: 'Retracement' });
			const extensionTab = screen.getByRole('tab', { name: 'Extension' });
			expect(retracementTab).toHaveAttribute('aria-selected', 'false');
			expect(extensionTab).toHaveAttribute('aria-selected', 'true');

			for (const level of DEFAULT_FIB_EXTENSION_LEVELS) {
				const expectedPercent = `${(level.ratio * 100).toFixed(1)}%`;
				expect(screen.getByTestId(`fib-level-row-${level.ratio}`)).toBeInTheDocument();
				expect(screen.getByText(expectedPercent)).toBeInTheDocument();
			}
		});

		it('switches between Retracement and Extension sub-tabs on click', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const retracementTab = screen.getByRole('tab', { name: 'Retracement' });
			const extensionTab = screen.getByRole('tab', { name: 'Extension' });

			// Initially Retracement
			expect(retracementTab).toHaveAttribute('aria-selected', 'true');
			expect(screen.getByTestId('fib-level-row-0.236')).toBeInTheDocument();
			expect(screen.queryByTestId('fib-level-row-4.236')).not.toBeInTheDocument();

			// Switch to Extension
			await fireEvent.click(extensionTab);
			expect(extensionTab).toHaveAttribute('aria-selected', 'true');
			expect(retracementTab).toHaveAttribute('aria-selected', 'false');
			expect(screen.getByTestId('fib-level-row-4.236')).toBeInTheDocument();
			expect(screen.queryByTestId('fib-level-row-0.236')).not.toBeInTheDocument();

			// Switch back to Retracement
			await fireEvent.click(retracementTab);
			expect(retracementTab).toHaveAttribute('aria-selected', 'true');
			expect(screen.getByTestId('fib-level-row-0.236')).toBeInTheDocument();
		});

		it('toggles a single retracement level and fires onFibLevelsChange', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnFibLevelsChange).toHaveBeenCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.618,
						enabled: false
					})
				])
			);

			// Toggling again re-enables it
			await fireEvent.click(row0618);
			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(2);
			expect(mockOnFibLevelsChange).toHaveBeenLastCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.618,
						enabled: true
					})
				])
			);
		});

		it('toggles level when clicking directly on checkbox element', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const checkbox0382 = screen.getByTestId('fib-checkbox-0.382');
			await fireEvent.click(checkbox0382);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnFibLevelsChange).toHaveBeenCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.382,
						enabled: false
					})
				])
			);
		});

		it('toggles an extension level when on extension tab', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					activeTool: 'extension',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const row2618 = screen.getByTestId('fib-level-row-2.618');
			await fireEvent.click(row2618);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnFibLevelsChange).toHaveBeenCalledWith(
				'extension',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 2.618,
						enabled: false
					})
				])
			);
		});

		it('toggles level using keyboard Enter / Space keydown on the row', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const row05 = screen.getByTestId('fib-level-row-0.5');
			await fireEvent.keyDown(row05, { key: 'Enter' });

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnFibLevelsChange).toHaveBeenCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.5,
						enabled: false
					})
				])
			);

			await fireEvent.keyDown(row05, { key: ' ' });
			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(2);
			expect(mockOnFibLevelsChange).toHaveBeenLastCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.5,
						enabled: true
					})
				])
			);
		});

		it('disables all levels and emits onFibLevelsChange when "Disable All" is clicked', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const disableAllBtn = screen.getByRole('button', { name: 'Disable All' });
			await fireEvent.click(disableAllBtn);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnFibLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels.every((l: FibLevelConfig) => l.enabled === false)).toBe(true);
		});

		it('enables all levels and emits onFibLevelsChange when "Enable All" is clicked', async () => {
			const customRetracement: FibLevelConfig[] = DEFAULT_FIB_RETRACEMENT_LEVELS.map((l) => ({
				...l,
				enabled: false
			}));

			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					retracementLevels: customRetracement,
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const enableAllBtn = screen.getByRole('button', { name: 'Enable All' });
			await fireEvent.click(enableAllBtn);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnFibLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels.every((l: FibLevelConfig) => l.enabled === true)).toBe(true);
		});

		it('restores default levels and emits onFibLevelsChange when "Reset to Defaults" is clicked', async () => {
			const modifiedLevels: FibLevelConfig[] = [
				{ ratio: 0.0, color: '#000000', enabled: false },
				{ ratio: 0.5, color: '#ffffff', enabled: false }
			];

			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					retracementLevels: modifiedLevels,
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const resetBtn = screen.getByRole('button', { name: /Reset to Defaults/i });
			await fireEvent.click(resetBtn);

			expect(mockOnFibLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnFibLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels).toHaveLength(DEFAULT_FIB_RETRACEMENT_LEVELS.length);
			expect(levels).toEqual(DEFAULT_FIB_RETRACEMENT_LEVELS);
		});

		it('displays disabled helper banner and prevents interactions when disabled is true', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					disabled: true,
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const banner = screen.getByTestId('fib-settings-disabled-banner');
			expect(banner).toBeInTheDocument();
			expect(banner).toHaveTextContent('Fibonacci settings are currently disabled.');

			expect(screen.getByRole('button', { name: 'Enable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: 'Disable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeDisabled();

			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnFibLevelsChange).not.toHaveBeenCalled();
		});

		it('displays helper banner and disables interactions when hasActiveDrawing is false', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					hasActiveDrawing: false,
					onFibLevelsChange: mockOnFibLevelsChange
				}
			});

			const banner = screen.getByTestId('fib-settings-disabled-banner');
			expect(banner).toBeInTheDocument();
			expect(banner).toHaveTextContent('No active Fibonacci drawing selected on chart.');

			expect(screen.getByRole('button', { name: 'Enable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: 'Disable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeDisabled();

			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnFibLevelsChange).not.toHaveBeenCalled();
		});

		it('invokes onClose when Close button is clicked in Fibonacci panel', async () => {
			render(ChartSettingsModal, {
				props: {
					open: true,
					initialSection: 'fibonacci',
					onClose: mockOnClose
				}
			});

			const closeButtons = screen.getAllByRole('button', { name: 'Close' });
			expect(closeButtons.length).toBeGreaterThanOrEqual(1);
			await fireEvent.click(closeButtons[0]);

			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});
	});
});
