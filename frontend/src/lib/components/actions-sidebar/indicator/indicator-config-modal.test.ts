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

	const bbConfig = {
		id: 'bb',
		label: 'Bollinger Bands',
		color: '#06b6d4',
		period: 20,
		stdDev: 2,
		enabled: true
	};

	const macdConfig = {
		id: 'macd',
		label: 'MACD',
		color: '#06b6d4',
		fast: 12,
		slow: 26,
		signal: 9,
		enabled: true
	};

	// DOM-presence check for the picker: bits-ui unmounts the popover content
	// when it closes (no forceMount here), so the sliders leave the DOM entirely.
	// `queryByRole` filters by accessibility visibility and is unreliable under
	// jsdom, so check raw DOM presence instead.
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

	it('right-aligns the color swatch control within the modal row', () => {
		render(IndicatorConfigModal, {
			props: { open: true, config: rsiConfig, onSave: mockOnSave, onReset: mockOnReset }
		});

		const swatch = screen.getByTestId('indicator-color-swatch');
		// The swatch row spans the remaining grid columns (label left) and the
		// control is pushed to the right edge of the modal. jsdom can't compute
		// layout, so the right-alignment class is the verifiable contract.
		const row = swatch.closest('.col-span-3');
		if (!row) throw new Error('color row wrapper not found');
		expect(row.className).toContain('justify-end');
	});

	it.each([
		{ config: { ...rsiConfig }, inputs: 1 },
		{ config: { ...bbConfig }, inputs: 2 },
		{ config: { ...macdConfig }, inputs: 3 }
	])('right-aligns the text/number input rows ($inputs inputs)', ({ config, inputs }) => {
		render(IndicatorConfigModal, {
			props: { open: true, config, onSave: mockOnSave, onReset: mockOnReset }
		});

		// Same right-alignment contract as the swatch row: each input lives in a
		// `col-span-3 flex justify-end` wrapper, so the control sits on the
		// right edge of the modal with its label on the left. The input is also
		// compact (`w-24` overrides the shared Input's default `w-full` via
		// tailwind-merge), so it does not stretch to fill the row.
		const numberInputs = document.querySelectorAll('input[type="number"]');
		expect(numberInputs).toHaveLength(inputs);
		for (const input of numberInputs) {
			const row = input.closest('.col-span-3');
			if (!row) throw new Error('input row wrapper not found');
			expect(row.className).toContain('justify-end');
			expect(input.className).toContain('w-24');
			expect(input.className).not.toContain('w-full');
		}
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

		// bits-ui applies the resolved floating-ui placement as data attributes
		// on the portaled content. With side="bottom" + align="end" the
		// placement is "bottom-end": the popover's right edge aligns with the
		// swatch's right edge, extending leftward below the button.
		await waitFor(() => {
			const content = document.querySelector('[data-slot="popover-content"]');
			if (!content) throw new Error('popover content not rendered');
			expect(content.getAttribute('data-side')).toBe('bottom');
			expect(content.getAttribute('data-align')).toBe('end');
		});
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
		const hexInput = screen.getByRole('textbox', { name: 'Hex color' });
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
