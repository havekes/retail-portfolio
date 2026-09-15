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

		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		expect(input).toBeInTheDocument();
		expect(input.value).toBe('1');

		expect(screen.getByTestId('preset-1x')).toBeInTheDocument();
		expect(screen.getByTestId('preset-1.5x')).toBeInTheDocument();
		expect(screen.getByTestId('preset-2x')).toBeInTheDocument();
		expect(screen.getByTestId('preset-3x')).toBeInTheDocument();
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
		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		expect(input.value).toBe('2');
	});

	it('initializes multiplier and extendLines from existing drawing', () => {
		const drawing: FibRetracementDrawing = {
			p1: { time: '2024-01-01', price: 100 },
			p2: { time: '2024-01-02', price: 200 },
			widthMultiplier: 2.5,
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

		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		expect(input.value).toBe('2.5');

		const checkbox = screen.getByTestId('extend-lines-checkbox');
		expect(checkbox).toHaveAttribute('data-state', 'checked');
	});

	it('clicking preset buttons updates the multiplier', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const preset15 = screen.getByTestId('preset-1.5x');
		await fireEvent.click(preset15);

		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		expect(input.value).toBe('1.5');

		const preset3 = screen.getByTestId('preset-3x');
		await fireEvent.click(preset3);
		expect(input.value).toBe('3');
	});

	it('adjusting custom numeric input updates multiplier value and saves correctly', async () => {
		render(FibWidthModal, {
			props: {
				open: true,
				tool: 'retracement',
				onSave: mockOnSave,
				onClose: mockOnClose
			}
		});

		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: '1.75' } });
		expect(input.value).toBe('1.75');

		const saveBtn = screen.getByTestId('save-btn');
		await fireEvent.click(saveBtn);

		expect(mockOnSave).toHaveBeenCalledWith('retracement', 1.75, false);
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

		const input = screen.getByTestId('fib-width-multiplier-input') as HTMLInputElement;
		expect(input.value).toBe('3');

		const resetBtn = screen.getByTestId('reset-default-btn');
		await fireEvent.click(resetBtn);

		expect(input.value).toBe('1');

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
