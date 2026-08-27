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
});
