import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import IndicatorConfigModal from './indicator-config-modal.svelte';

describe('IndicatorConfigModal Component', () => {
	let mockOnSave = vi.fn<(id: string, updatedConfig: Record<string, unknown>) => void>();
	let mockOnReset = vi.fn<(id: string) => void>();

	const rsiConfig = {
		id: 'rsi',
		label: 'RSI',
		color: '#06b6d4',
		period: 14,
		enabled: true
	};

	beforeEach(() => {
		vi.clearAllMocks();
		mockOnSave = vi.fn<(id: string, updatedConfig: Record<string, unknown>) => void>();
		mockOnReset = vi.fn<(id: string) => void>();
	});

	it('renders the reset button alongside Save settings when a config is open', () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		expect(screen.getByText('RSI Settings')).toBeInTheDocument();
		expect(screen.getByTestId('reset-indicator-btn')).toBeInTheDocument();
		expect(screen.getByText('Reset to defaults')).toBeInTheDocument();
		expect(screen.getByText('Save settings')).toBeInTheDocument();
	});

	it('invokes onReset with the open indicator id and keeps the dialog open', async () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		await fireEvent.click(screen.getByTestId('reset-indicator-btn'));

		expect(mockOnReset).toHaveBeenCalledWith('rsi');
		expect(mockOnSave).not.toHaveBeenCalled();

		// Reset does not close the dialog — the restored values stay visible.
		expect(screen.getByText('RSI Settings')).toBeInTheDocument();
		expect(screen.getByTestId('reset-indicator-btn')).toBeInTheDocument();
	});

	it('does not render the reset button when no config is open', () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: null, onSave: mockOnSave, onReset: mockOnReset }
		});

		expect(screen.queryByTestId('reset-indicator-btn')).not.toBeInTheDocument();
		expect(screen.queryByText('Save settings')).not.toBeInTheDocument();
	});
});
