import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import FibonacciSettingsDialog from './fibonacci-settings-dialog.svelte';
import {
	DEFAULT_FIB_RETRACEMENT_LEVELS,
	DEFAULT_FIB_EXTENSION_LEVELS,
	type FibLevelConfig,
	type FibToolType
} from '$lib/utils/finance/fibonacci';

describe('FibonacciSettingsDialog Component', () => {
	let mockOnLevelsChange = vi.fn<(tool: FibToolType, levels: FibLevelConfig[]) => void>();
	let mockOnClose = vi.fn<() => void>();

	beforeEach(() => {
		vi.clearAllMocks();
		mockOnLevelsChange = vi.fn<(tool: FibToolType, levels: FibLevelConfig[]) => void>();
		mockOnClose = vi.fn<() => void>();
	});

	describe('Rendering & Visibility', () => {
		it('does not render dialog content when open is false', () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: false
				}
			});

			expect(screen.queryByText('Fibonacci Settings')).not.toBeInTheDocument();
		});

		it('renders dialog header, tab switcher, and retracement levels by default when open', () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange,
					onClose: mockOnClose
				}
			});

			expect(screen.getByText('Fibonacci Settings')).toBeInTheDocument();
			expect(
				screen.getByText(
					'Configure visible levels and colors for Fibonacci retracement and extension tools.'
				)
			).toBeInTheDocument();

			// Tab selector buttons
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

			// Badges
			const colorBadges = screen.getAllByTestId('fib-level-color-badge');
			expect(colorBadges.length).toBe(DEFAULT_FIB_RETRACEMENT_LEVELS.length);
		});

		it('opens with Extension tab selected when activeTool is "extension"', () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					activeTool: 'extension',
					onLevelsChange: mockOnLevelsChange
				}
			});

			const retracementTab = screen.getByRole('tab', { name: 'Retracement' });
			const extensionTab = screen.getByRole('tab', { name: 'Extension' });
			expect(retracementTab).toHaveAttribute('aria-selected', 'false');
			expect(extensionTab).toHaveAttribute('aria-selected', 'true');

			// Standard Extension levels (0.0 to 4.236)
			for (const level of DEFAULT_FIB_EXTENSION_LEVELS) {
				const expectedPercent = `${(level.ratio * 100).toFixed(1)}%`;
				expect(screen.getByTestId(`fib-level-row-${level.ratio}`)).toBeInTheDocument();
				expect(screen.getByText(expectedPercent)).toBeInTheDocument();
			}
		});

		it('invokes onClose when Close button is clicked', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onClose: mockOnClose
				}
			});

			const closeButtons = screen.getAllByRole('button', { name: 'Close' });
			expect(closeButtons.length).toBeGreaterThanOrEqual(1);
			await fireEvent.click(closeButtons[0]);

			expect(mockOnClose).toHaveBeenCalledTimes(1);
		});
	});

	describe('Tab Switching', () => {
		it('switches between Retracement and Extension tabs on click', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
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
	});

	describe('Level Visibility Toggling', () => {
		it('toggles a single retracement level and fires onLevelsChange callback', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnLevelsChange).toHaveBeenCalledWith(
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
			expect(mockOnLevelsChange).toHaveBeenCalledTimes(2);
			expect(mockOnLevelsChange).toHaveBeenLastCalledWith(
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
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const checkbox0382 = screen.getByTestId('fib-checkbox-0.382');
			await fireEvent.click(checkbox0382);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnLevelsChange).toHaveBeenCalledWith(
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
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					activeTool: 'extension',
					onLevelsChange: mockOnLevelsChange
				}
			});

			const row2618 = screen.getByTestId('fib-level-row-2.618');
			await fireEvent.click(row2618);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnLevelsChange).toHaveBeenCalledWith(
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
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const row05 = screen.getByTestId('fib-level-row-0.5');
			await fireEvent.keyDown(row05, { key: 'Enter' });

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			expect(mockOnLevelsChange).toHaveBeenCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.5,
						enabled: false
					})
				])
			);

			await fireEvent.keyDown(row05, { key: ' ' });
			expect(mockOnLevelsChange).toHaveBeenCalledTimes(2);
			expect(mockOnLevelsChange).toHaveBeenLastCalledWith(
				'retracement',
				expect.arrayContaining([
					expect.objectContaining({
						ratio: 0.5,
						enabled: true
					})
				])
			);
		});
	});

	describe('Batch Actions', () => {
		it('disables all levels and emits onLevelsChange when "Disable All" is clicked', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const disableAllBtn = screen.getByRole('button', { name: 'Disable All' });
			await fireEvent.click(disableAllBtn);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels.every((l: FibLevelConfig) => l.enabled === false)).toBe(true);
		});

		it('enables all levels and emits onLevelsChange when "Enable All" is clicked', async () => {
			const customRetracement: FibLevelConfig[] = DEFAULT_FIB_RETRACEMENT_LEVELS.map((l) => ({
				...l,
				enabled: false
			}));

			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					retracementLevels: customRetracement,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const enableAllBtn = screen.getByRole('button', { name: 'Enable All' });
			await fireEvent.click(enableAllBtn);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels.every((l: FibLevelConfig) => l.enabled === true)).toBe(true);
		});

		it('restores default levels and emits onLevelsChange when "Reset to Defaults" is clicked', async () => {
			const modifiedLevels: FibLevelConfig[] = [
				{ ratio: 0.0, color: '#000000', enabled: false },
				{ ratio: 0.5, color: '#ffffff', enabled: false }
			];

			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					retracementLevels: modifiedLevels,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const resetBtn = screen.getByRole('button', { name: /Reset to Defaults/i });
			await fireEvent.click(resetBtn);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnLevelsChange.mock.calls[0];
			expect(tool).toBe('retracement');
			expect(levels).toHaveLength(DEFAULT_FIB_RETRACEMENT_LEVELS.length);
			expect(levels).toEqual(DEFAULT_FIB_RETRACEMENT_LEVELS);
		});

		it('resets extension levels to defaults when on extension tab', async () => {
			const modifiedLevels: FibLevelConfig[] = [{ ratio: 0.0, color: '#000000', enabled: false }];

			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					activeTool: 'extension',
					extensionLevels: modifiedLevels,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const resetBtn = screen.getByRole('button', { name: /Reset to Defaults/i });
			await fireEvent.click(resetBtn);

			expect(mockOnLevelsChange).toHaveBeenCalledTimes(1);
			const [tool, levels] = mockOnLevelsChange.mock.calls[0];
			expect(tool).toBe('extension');
			expect(levels).toEqual(DEFAULT_FIB_EXTENSION_LEVELS);
		});

		it('does not mutate constant default objects in place when performing actions', async () => {
			const originalRetracementCopy = JSON.parse(JSON.stringify(DEFAULT_FIB_RETRACEMENT_LEVELS));
			const originalExtensionCopy = JSON.parse(JSON.stringify(DEFAULT_FIB_EXTENSION_LEVELS));

			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const disableAllBtn = screen.getByRole('button', { name: 'Disable All' });
			await fireEvent.click(disableAllBtn);

			const resetBtn = screen.getByRole('button', { name: /Reset to Defaults/i });
			await fireEvent.click(resetBtn);

			expect(DEFAULT_FIB_RETRACEMENT_LEVELS).toEqual(originalRetracementCopy);
			expect(DEFAULT_FIB_EXTENSION_LEVELS).toEqual(originalExtensionCopy);
		});
	});

	describe('Custom Level Configurations', () => {
		it('renders custom level configurations passed via props', () => {
			const customLevels: FibLevelConfig[] = [
				{ ratio: 0.333, color: '#FF5722', enabled: true },
				{ ratio: 0.667, color: '#9C27B0', enabled: false }
			];

			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					retracementLevels: customLevels,
					onLevelsChange: mockOnLevelsChange
				}
			});

			expect(screen.getByTestId('fib-level-row-0.333')).toBeInTheDocument();
			expect(screen.getByTestId('fib-level-row-0.667')).toBeInTheDocument();
			expect(screen.getByText('33.3%')).toBeInTheDocument();
			expect(screen.getByText('66.7%')).toBeInTheDocument();

			const badges = screen.getAllByTestId('fib-level-color-badge');
			expect(badges[0]).toHaveStyle('background-color: #FF5722');
			expect(badges[1]).toHaveStyle('background-color: #9C27B0');
		});
	});

	describe('Disabled & No Active Drawing States', () => {
		it('displays disabled helper banner and prevents interactions when disabled is true', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					disabled: true,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const banner = screen.getByTestId('fib-settings-disabled-banner');
			expect(banner).toBeInTheDocument();
			expect(banner).toHaveTextContent('Fibonacci settings are currently disabled.');

			// Buttons should be disabled
			expect(screen.getByRole('button', { name: 'Enable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: 'Disable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeDisabled();

			// Clicking row does not trigger onLevelsChange
			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnLevelsChange).not.toHaveBeenCalled();
		});

		it('displays helper banner and disables interactions when hasActiveDrawing is false', async () => {
			render(FibonacciSettingsDialog, {
				props: {
					open: true,
					hasActiveDrawing: false,
					onLevelsChange: mockOnLevelsChange
				}
			});

			const banner = screen.getByTestId('fib-settings-disabled-banner');
			expect(banner).toBeInTheDocument();
			expect(banner).toHaveTextContent('No active Fibonacci drawing selected on chart.');

			// Buttons should be disabled
			expect(screen.getByRole('button', { name: 'Enable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: 'Disable All' })).toBeDisabled();
			expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeDisabled();

			// Clicking row does not trigger onLevelsChange
			const row0618 = screen.getByTestId('fib-level-row-0.618');
			await fireEvent.click(row0618);

			expect(mockOnLevelsChange).not.toHaveBeenCalled();
		});
	});
});
