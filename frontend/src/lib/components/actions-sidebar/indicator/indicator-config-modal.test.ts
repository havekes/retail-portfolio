import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import IndicatorConfigModal from './indicator-config-modal.svelte';
import IndicatorConfigModalHarness from './indicator-config-modal.test-harness.svelte';

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

	// DOM-presence check for the picker: bits-ui's floating layer hides portaled
	// content with `visibility: hidden` under jsdom (floating-ui can't measure
	// layout), so `queryByRole` (which filters by accessibility visibility) is
	// unreliable here. The elements are present in the DOM regardless.
	const pickerInDom = () =>
		!!document.querySelector('[role="slider"][aria-label="Saturation and Brightness"]');

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

	it('renders the color control as a swatch showing the current color with the picker closed', () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		const swatch = screen.getByTestId('indicator-color-swatch');
		expect(swatch).toBeInTheDocument();
		// jsdom normalizes the #06b6d4 inline background to rgb().
		expect(swatch.style.backgroundColor).toBe('rgb(6, 182, 212)');
		// The full picker is not mounted until the swatch is clicked.
		expect(pickerInDom()).toBe(false);
	});

	it('opens the color picker dropdown when the swatch is clicked', async () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		const swatch = screen.getByTestId('indicator-color-swatch');
		expect(swatch.getAttribute('aria-expanded')).toBe('false');
		await fireEvent.click(swatch);

		expect(pickerInDom()).toBe(true);
		expect(screen.getByTestId('indicator-color-swatch').getAttribute('aria-expanded')).toBe('true');
	});

	it('updates the swatch color live when a new hex value is typed in the picker', async () => {
		// Local copy so the binding does not leak into the other tests.
		const liveConfig = { ...rsiConfig };
		// The harness passes the config through $state, mirroring the real parent
		// (indicator-group.svelte) so the swatch re-renders on binding updates.
		render(IndicatorConfigModalHarness, {
			props: { config: liveConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		await fireEvent.click(screen.getByTestId('indicator-color-swatch'));
		const hexInput = screen.getByDisplayValue('#06b6d4');
		await fireEvent.input(hexInput, { target: { value: '#ff0000' } });

		// The swatch reflects the new color live (jsdom normalizes to rgb()).
		expect(screen.getByTestId('indicator-color-swatch').style.backgroundColor).toBe(
			'rgb(255, 0, 0)'
		);

		// The bound config.color carries through the unchanged save path.
		await fireEvent.click(screen.getByText('Save settings'));
		expect(mockOnSave).toHaveBeenCalledWith('rsi', expect.objectContaining({ color: '#FF0000' }));
	});

	it('closes the color picker dropdown on Escape', async () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		const swatch = () => screen.getByTestId('indicator-color-swatch');
		await fireEvent.click(swatch());
		expect(pickerInDom()).toBe(true);

		// bits-ui's Popover closes on Escape by default (same handleClose path
		// as outside-click dismissal).
		await fireEvent.keyDown(document, { key: 'Escape' });
		await waitFor(() => {
			expect(swatch().getAttribute('aria-expanded')).toBe('false');
		});
		await waitFor(() => {
			expect(pickerInDom()).toBe(false);
		});

		// Reopening after a close still works.
		await fireEvent.click(swatch());
		expect(pickerInDom()).toBe(true);
	});
});
