import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import FibWidthModal from './fib-width-modal.svelte';
import type { FibRetracementDrawing, FibToolType } from '$lib/utils/finance/fibonacci';

describe('FibWidthModal Component', () => {
	let mockOnSave =
		vi.fn<(tool: FibToolType, multiplier: number | null, extendLines?: boolean) => void>();
	let mockOnClose = vi.fn<() => void>();

	beforeEach(() => {
		vi.clearAllMocks();
		mockOnSave = vi.fn();
		mockOnClose = vi.fn();
	});

	it('does not render dialog content when open is false', () => {
		render(FibWidthModal, {
			props: {
				open: false,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		expect(screen.queryByTestId('fib-width-modal')).not.toBeInTheDocument();
	});

	it('renders dialog title and controls for Retracement with default 1x multiplier', () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		expect(screen.getByTestId('fib-width-modal')).toBeInTheDocument();
		expect(screen.getByTestId('fib-width-modal-title')).toHaveTextContent(
			'Fibonacci Retracement Width'
		);

		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		expect(slider).toBeInTheDocument();
		expect(slider.value).toBe('2');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('1x');

		expect(screen.getByTestId('preset-0.25x')).toHaveTextContent('.25x');
		expect(screen.getByTestId('preset-0.5x')).toHaveTextContent('.5x');
		expect(screen.getByTestId('preset-1x')).toHaveTextContent('1x');
		expect(screen.getByTestId('preset-1.5x')).toHaveTextContent('1.5x');
		expect(screen.getByTestId('preset-2x')).toHaveTextContent('2x');
		expect(screen.getByTestId('preset-3x')).toHaveTextContent('3x');
		expect(screen.getByTestId('extend-lines-checkbox')).toBeInTheDocument();
		expect(screen.getByTestId('reset-default-btn')).toBeInTheDocument();
	});

	it('renders dialog title and controls for Extension with default 2x multiplier', () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'extension',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		expect(screen.getByTestId('fib-width-modal-title')).toHaveTextContent(
			'Fibonacci Extension Width'
		);
		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		expect(slider.value).toBe('4');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('2x');
	});

	it('initializes multiplier and extendLines from existing drawing', () => {
		const drawing: FibRetracementDrawing = {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			widthMultiplier: 0.5,
			extendLines: true
		};

		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				drawing,
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		expect(slider.value).toBe('1');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('.5x');

		const checkbox = screen.getByTestId('extend-lines-checkbox');
		expect(checkbox).toHaveAttribute('data-state', 'checked');
	});

	it('clicking stop buttons updates the slider and multiplier', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const preset025 = screen.getByTestId('preset-0.25x');
		await fireEvent.click(preset025);

		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		expect(slider.value).toBe('0');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('.25x');

		const preset3 = screen.getByTestId('preset-3x');
		await fireEvent.click(preset3);
		expect(slider.value).toBe('5');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('3x');
	});

	it('adjusting slider via input event updates multiplier value and saves correctly', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		await fireEvent.input(slider, { target: { value: '3' } });
		expect(slider.value).toBe('3');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('1.5x');

		const saveBtn = screen.getByTestId('save-btn');
		await fireEvent.click(saveBtn);

		expect(mockOnSave).toHaveBeenCalledWith('retracement', 1.5, false);
	});

	it('toggling extendLines checkbox saves with extendLines: true', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const checkbox = screen.getByTestId('extend-lines-checkbox');
		await fireEvent.click(checkbox);

		const saveBtn = screen.getByTestId('save-btn');
		await fireEvent.click(saveBtn);

		expect(mockOnSave).toHaveBeenCalledWith('retracement', 1, true);
	});

	it('reset button resets multiplier to default', async () => {
		const drawing: FibRetracementDrawing = {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			widthMultiplier: 3.0,
			extendLines: true
		};

		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				drawing,
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const slider = screen.getByTestId('fib-width-slider') as HTMLInputElement;
		expect(slider.value).toBe('5');

		const resetBtn = screen.getByTestId('reset-default-btn');
		await fireEvent.click(resetBtn);

		expect(slider.value).toBe('2');
		expect(screen.getByTestId('fib-width-multiplier-display')).toHaveTextContent('1x');

		const saveBtn = screen.getByTestId('save-btn');
		await fireEvent.click(saveBtn);

		expect(mockOnSave).toHaveBeenCalledWith('retracement', 1, false);
	});

	it('clicking Cancel invokes onClose without calling onSave', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const cancelBtn = screen.getByTestId('cancel-btn');
		await fireEvent.click(cancelBtn);

		expect(mockOnSave).not.toHaveBeenCalled();
		expect(mockOnClose).toHaveBeenCalledTimes(1);
	});
});
