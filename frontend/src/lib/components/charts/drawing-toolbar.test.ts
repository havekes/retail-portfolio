import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import DrawingToolbar from './drawing-toolbar.svelte';

describe('DrawingToolbar Component', () => {
	it('renders Impulse Wave, Corrective Wave, Fib Retrace, and Fib Extend tool buttons', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		const retraceBtn = screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i });
		const extendBtn = screen.getByRole('button', { name: /Toggle Fib Extend drawing/i });

		expect(impulseBtn).toBeInTheDocument();
		expect(impulseBtn).toHaveAttribute('title', 'Impulse Wave');

		expect(correctiveBtn).toBeInTheDocument();
		expect(correctiveBtn).toHaveAttribute('title', 'Corrective Wave');

		expect(retraceBtn).toBeInTheDocument();
		expect(retraceBtn).toHaveAttribute('title', 'Fibonacci Retracement');

		expect(extendBtn).toBeInTheDocument();
		expect(extendBtn).toHaveAttribute('title', 'Fibonacci Extension');
	});

	it('opens impulse wave dropdown menu with single-wave previews (I, ①, 1) and triggers onSelectWaveDegree', async () => {
		const onSelectWaveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectWaveDegree
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		await fireEvent.click(impulseBtn);

		expect(await screen.findByText('Degree')).toBeInTheDocument();

		// Check right-aligned previews
		expect(screen.getByText('Cycle')).toBeInTheDocument();
		expect(screen.getByText('I')).toBeInTheDocument();
		expect(screen.getByText('Primary')).toBeInTheDocument();
		expect(screen.getByText('①')).toBeInTheDocument();
		expect(screen.getByText('Intermediate')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();

		const cycleOption = screen.getByText('Cycle');
		await fireEvent.click(cycleOption);

		expect(onSelectWaveDegree).toHaveBeenCalledWith('cycle', 'impulse');
	});

	it('triggers onSelectWaveDegree when Primary Degree is selected from impulse dropdown', async () => {
		const onSelectWaveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectWaveDegree
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		await fireEvent.click(impulseBtn);

		const primaryOption = await screen.findByText('Primary');
		await fireEvent.click(primaryOption);

		expect(onSelectWaveDegree).toHaveBeenCalledWith('primary', 'impulse');
	});

	it('triggers onSelectWaveDegree when Intermediate Degree is selected from impulse dropdown', async () => {
		const onSelectWaveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectWaveDegree
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		await fireEvent.click(impulseBtn);

		const intermediateOption = await screen.findByText('Intermediate');
		await fireEvent.click(intermediateOption);

		expect(onSelectWaveDegree).toHaveBeenCalledWith('intermediate', 'impulse');
	});

	it('opens corrective wave dropdown menu with single-wave previews (A, Ⓐ, (A)) and triggers onSelectCorrectiveDegree', async () => {
		const onSelectCorrectiveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectCorrectiveDegree
			}
		});

		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		await fireEvent.click(correctiveBtn);

		expect(await screen.findByText('Degree')).toBeInTheDocument();

		// Check right-aligned corrective previews
		expect(screen.getByText('Cycle')).toBeInTheDocument();
		expect(screen.getByText('A')).toBeInTheDocument();
		expect(screen.getByText('Primary')).toBeInTheDocument();
		expect(screen.getByText('Ⓐ')).toBeInTheDocument();
		expect(screen.getByText('Intermediate')).toBeInTheDocument();
		expect(screen.getByText('(A)')).toBeInTheDocument();

		const cycleOption = screen.getByText('Cycle');
		await fireEvent.click(cycleOption);

		expect(onSelectCorrectiveDegree).toHaveBeenCalledWith('cycle');
	});

	it('triggers onSelectCorrectiveDegree when Primary Degree is selected from corrective dropdown', async () => {
		const onSelectCorrectiveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectCorrectiveDegree
			}
		});

		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		await fireEvent.click(correctiveBtn);

		const primaryOption = await screen.findByText('Primary');
		await fireEvent.click(primaryOption);

		expect(onSelectCorrectiveDegree).toHaveBeenCalledWith('primary');
	});

	it('triggers onSelectCorrectiveDegree when Intermediate Degree is selected from corrective dropdown', async () => {
		const onSelectCorrectiveDegree = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onSelectCorrectiveDegree
			}
		});

		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		await fireEvent.click(correctiveBtn);

		const intermediateOption = await screen.findByText('Intermediate');
		await fireEvent.click(intermediateOption);

		expect(onSelectCorrectiveDegree).toHaveBeenCalledWith('intermediate');
	});

	it('highlights Impulse Wave button when isDrawingWave is true and activeWaveType is impulse', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				activeWaveType: 'impulse',
				isDrawingWave: true,
				activeFibTool: null,
				isDrawingFib: false
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		expect(impulseBtn.className).toContain('bg-primary');
		expect(correctiveBtn.className).not.toContain('bg-primary');
	});

	it('highlights Corrective Wave button when isDrawingWave is true and activeWaveType is corrective', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				activeWaveType: 'corrective',
				isDrawingWave: true,
				activeFibTool: null,
				isDrawingFib: false
			}
		});

		const impulseBtn = screen.getByRole('button', { name: 'Impulse Wave' });
		const correctiveBtn = screen.getByRole('button', { name: 'Corrective Wave' });
		expect(correctiveBtn.className).toContain('bg-primary');
		expect(impulseBtn.className).not.toContain('bg-primary');
	});

	it('triggers onToggleFib with retracement when Fib Retrace button is clicked', async () => {
		const onToggleFib = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onToggleFib
			}
		});

		const retraceBtn = screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i });
		await fireEvent.click(retraceBtn);

		expect(onToggleFib).toHaveBeenCalledWith('retracement');
	});

	it('triggers onToggleFib with extension when Fib Extend button is clicked', async () => {
		const onToggleFib = vi.fn();
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false,
				onToggleFib
			}
		});

		const extendBtn = screen.getByRole('button', { name: /Toggle Fib Extend drawing/i });
		await fireEvent.click(extendBtn);

		expect(onToggleFib).toHaveBeenCalledWith('extension');
	});

	it('highlights Fib Retrace button when isDrawingFib is true and activeFibTool is retracement', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: 'retracement',
				isDrawingFib: true
			}
		});

		const retraceBtn = screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i });
		const extendBtn = screen.getByRole('button', { name: /Toggle Fib Extend drawing/i });
		expect(retraceBtn.className).toContain('bg-primary');
		expect(extendBtn.className).not.toContain('bg-primary');
	});

	it('highlights Fib Extend button when isDrawingFib is true and activeFibTool is extension', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: 'extension',
				isDrawingFib: true
			}
		});

		const retraceBtn = screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i });
		const extendBtn = screen.getByRole('button', { name: /Toggle Fib Extend drawing/i });
		expect(extendBtn.className).toContain('bg-primary');
		expect(retraceBtn.className).not.toContain('bg-primary');
	});

	it('renders Save snapshot button with correct title and triggers onSave when clicked', async () => {
		const onSave = vi.fn();
		render(DrawingToolbar, {
			props: {
				onSave
			}
		});

		const saveBtn = screen.getByRole('button', { name: 'Save snapshot' });
		expect(saveBtn).toBeInTheDocument();
		expect(saveBtn).toHaveAttribute('title', 'Save snapshot');

		await fireEvent.click(saveBtn);
		expect(onSave).toHaveBeenCalledTimes(1);
	});

	it('renders Save snapshot button with Saved title and check icon when saveFeedback is saved', () => {
		render(DrawingToolbar, {
			props: {
				saveFeedback: 'saved'
			}
		});

		const saveBtn = screen.getByRole('button', { name: 'Save snapshot' });
		expect(saveBtn).toBeInTheDocument();
		expect(saveBtn).toHaveAttribute('title', 'Saved');
		const svg = saveBtn.querySelector('svg');
		expect(svg).toBeInTheDocument();
		expect(svg?.classList.contains('lucide-check')).toBe(true);
	});

	it('renders timeline toggle button with correct aria-label and title and triggers onToggleTimeline', async () => {
		const onToggleTimeline = vi.fn();
		render(DrawingToolbar, {
			props: {
				onToggleTimeline
			}
		});

		const timelineBtn = screen.getByRole('button', { name: 'Toggle rewind timeline' });
		expect(timelineBtn).toBeInTheDocument();
		expect(timelineBtn).toHaveAttribute('title', 'Rewind Timeline');

		await fireEvent.click(timelineBtn);
		expect(onToggleTimeline).toHaveBeenCalledTimes(1);
	});

	it('renders Measure button with correct title and triggers onMeasureSelect', async () => {
		const onMeasureSelect = vi.fn();
		render(DrawingToolbar, { props: { onMeasureSelect } });

		const measureBtn = screen.getByRole('button', { name: 'Toggle Measure drawing' });
		expect(measureBtn).toBeInTheDocument();
		expect(measureBtn).toHaveAttribute('title', 'Measure');

		await fireEvent.click(measureBtn);
		expect(onMeasureSelect).toHaveBeenCalledTimes(1);
	});

	it('highlights the Measure button only while Measure drawing is active', () => {
		const { rerender } = render(DrawingToolbar, {
			props: { isDrawingMeasure: false }
		});

		const measureBtn = screen.getByRole('button', { name: 'Toggle Measure drawing' });
		expect(measureBtn.className).not.toContain('bg-primary');

		rerender({ isDrawingMeasure: true });
		expect(measureBtn.className).toContain('bg-primary');
	});

	it('renders Horizontal Line button with correct title and triggers onHorizontalLineSelect', async () => {
		const onHorizontalLineSelect = vi.fn();
		render(DrawingToolbar, { props: { onHorizontalLineSelect } });

		const lineBtn = screen.getByRole('button', { name: 'Toggle Horizontal Line drawing' });
		expect(lineBtn).toBeInTheDocument();
		expect(lineBtn).toHaveAttribute('title', 'Horizontal Line');

		await fireEvent.click(lineBtn);
		expect(onHorizontalLineSelect).toHaveBeenCalledTimes(1);
	});

	it('highlights the Horizontal Line button only while its drawing mode is active', () => {
		const { rerender } = render(DrawingToolbar, {
			props: { isDrawingHorizontalLine: false }
		});

		const lineBtn = screen.getByRole('button', { name: 'Toggle Horizontal Line drawing' });
		expect(lineBtn.className).not.toContain('bg-primary');

		rerender({ isDrawingHorizontalLine: true });
		expect(lineBtn.className).toContain('bg-primary');
	});

	it('renders Line button with correct title and triggers onLineSelect', async () => {
		const onLineSelect = vi.fn();
		render(DrawingToolbar, { props: { onLineSelect } });

		const lineBtn = screen.getByRole('button', { name: 'Toggle Line drawing' });
		expect(lineBtn).toBeInTheDocument();
		expect(lineBtn).toHaveAttribute('title', 'Line');

		await fireEvent.click(lineBtn);
		expect(onLineSelect).toHaveBeenCalledTimes(1);
	});

	it('highlights the Line button only while its drawing mode is active', () => {
		const { rerender } = render(DrawingToolbar, {
			props: { isDrawingLine: false }
		});

		const lineBtn = screen.getByRole('button', { name: 'Toggle Line drawing' });
		expect(lineBtn.className).not.toContain('bg-primary');

		rerender({ isDrawingLine: true });
		expect(lineBtn.className).toContain('bg-primary');
	});

	it('highlights timeline toggle button when isTimelineVisible is true', () => {
		const { rerender } = render(DrawingToolbar, {
			props: {
				isTimelineVisible: false
			}
		});

		const timelineBtn = screen.getByRole('button', { name: 'Toggle rewind timeline' });
		expect(timelineBtn.className).not.toContain('bg-primary');

		rerender({ isTimelineVisible: true });
		expect(timelineBtn.className).toContain('bg-primary');
	});

	it('renders Horizontal Line button with dedicated HorizontalLineIcon SVG', () => {
		render(DrawingToolbar);

		const lineBtn = screen.getByRole('button', { name: 'Toggle Horizontal Line drawing' });
		const lineSvg = lineBtn.querySelector('svg');
		expect(lineSvg).toBeInTheDocument();
		const lineEl = lineSvg?.querySelector('line');
		expect(lineEl).toHaveAttribute('x1', '3');
		expect(lineEl).toHaveAttribute('y1', '12');
		expect(lineEl).toHaveAttribute('x2', '21');
		expect(lineEl).toHaveAttribute('y2', '12');
	});

	it('renders Line button with dedicated LineIcon SVG', () => {
		render(DrawingToolbar);

		const lineBtn = screen.getByRole('button', { name: 'Toggle Line drawing' });
		const lineSvg = lineBtn.querySelector('svg');
		expect(lineSvg).toBeInTheDocument();
		const lineEl = lineSvg?.querySelector('line');
		expect(lineEl).toHaveAttribute('x1', '5');
		expect(lineEl).toHaveAttribute('y1', '19');
		expect(lineEl).toHaveAttribute('x2', '19');
		expect(lineEl).toHaveAttribute('y2', '5');
	});

	it('renders Undo and Redo buttons with shortcut tooltips and disabled state by default', () => {
		render(DrawingToolbar);

		const undoBtn = screen.getByRole('button', { name: 'Undo' });
		expect(undoBtn).toBeInTheDocument();
		expect(undoBtn).toHaveAttribute('title', 'Undo (Ctrl+Z / ⌘Z)');
		expect(undoBtn).toBeDisabled();

		const redoBtn = screen.getByRole('button', { name: 'Redo' });
		expect(redoBtn).toBeInTheDocument();
		expect(redoBtn).toHaveAttribute('title', 'Redo (Ctrl+Y / ⌘Y)');
		expect(redoBtn).toBeDisabled();
	});

	it('enables Undo and Redo buttons when canUndo and canRedo are true and triggers callbacks', async () => {
		const onUndo = vi.fn();
		const onRedo = vi.fn();

		const { rerender } = render(DrawingToolbar, {
			props: {
				canUndo: true,
				canRedo: true,
				onUndo,
				onRedo
			}
		});

		const undoBtn = screen.getByRole('button', { name: 'Undo' });
		const redoBtn = screen.getByRole('button', { name: 'Redo' });

		expect(undoBtn).toBeEnabled();
		expect(redoBtn).toBeEnabled();

		await fireEvent.click(undoBtn);
		expect(onUndo).toHaveBeenCalledTimes(1);

		await fireEvent.click(redoBtn);
		expect(onRedo).toHaveBeenCalledTimes(1);

		// When disabled, clicking should not trigger callbacks
		rerender({ canUndo: false, canRedo: false });
		expect(undoBtn).toBeDisabled();
		expect(redoBtn).toBeDisabled();

		await fireEvent.click(undoBtn);
		await fireEvent.click(redoBtn);
		expect(onUndo).toHaveBeenCalledTimes(1);
		expect(onRedo).toHaveBeenCalledTimes(1);
	});

	it('delegates actions to service when service prop is provided', async () => {
		const mockService = {
			activeWaveDegree: 'cycle' as const,
			activeWaveType: 'impulse' as const,
			isDrawingWave: false,
			isDrawingWaveEffective: false,
			activeFibTool: 'retracement' as const,
			isDrawingFib: false,
			isDrawingFibEffective: false,
			isDrawingMeasure: false,
			isDrawingMeasureEffective: false,
			isDrawingHorizontalLine: false,
			isDrawingHorizontalLineEffective: false,
			isDrawingLine: false,
			isDrawingLineEffective: false,
			isTimelineVisible: false,
			canUndo: true,
			canRedo: true,
			saveFeedback: 'idle' as const,
			selectWaveDegree: vi.fn(),
			toggleFib: vi.fn(),
			toggleMeasure: vi.fn(),
			toggleHorizontalLine: vi.fn(),
			toggleLine: vi.fn(),
			handleUndo: vi.fn(),
			handleRedo: vi.fn(),
			handleSaveSnapshot: vi.fn(),
			toggleTimeline: vi.fn()
		};

		render(DrawingToolbar, {
			props: {
				/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
				service: mockService as any
			}
		});

		// Fib retracement click
		const fibBtn = screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i });
		await fireEvent.click(fibBtn);
		expect(mockService.toggleFib).toHaveBeenCalledWith('retracement');

		// Measure click
		const measureBtn = screen.getByRole('button', { name: /Toggle Measure drawing/i });
		await fireEvent.click(measureBtn);
		expect(mockService.toggleMeasure).toHaveBeenCalledTimes(1);

		// Horizontal line click
		const hLineBtn = screen.getByRole('button', { name: /Toggle Horizontal Line drawing/i });
		await fireEvent.click(hLineBtn);
		expect(mockService.toggleHorizontalLine).toHaveBeenCalledTimes(1);

		// Line click
		const lineBtn = screen.getByRole('button', { name: /Toggle Line drawing/i });
		await fireEvent.click(lineBtn);
		expect(mockService.toggleLine).toHaveBeenCalledTimes(1);

		// Undo click
		const undoBtn = screen.getByRole('button', { name: 'Undo' });
		await fireEvent.click(undoBtn);
		expect(mockService.handleUndo).toHaveBeenCalledTimes(1);

		// Redo click
		const redoBtn = screen.getByRole('button', { name: 'Redo' });
		await fireEvent.click(redoBtn);
		expect(mockService.handleRedo).toHaveBeenCalledTimes(1);

		// Save click
		const saveBtn = screen.getByRole('button', { name: 'Save snapshot' });
		await fireEvent.click(saveBtn);
		expect(mockService.handleSaveSnapshot).toHaveBeenCalledTimes(1);

		// Timeline click
		const timelineBtn = screen.getByRole('button', { name: 'Toggle rewind timeline' });
		await fireEvent.click(timelineBtn);
		expect(mockService.toggleTimeline).toHaveBeenCalledTimes(1);
	});
});
