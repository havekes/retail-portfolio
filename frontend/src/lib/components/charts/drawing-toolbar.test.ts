import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import DrawingToolbar from './drawing-toolbar.svelte';

describe('DrawingToolbar Component', () => {
	it('renders Elliott Wave, Fib Retrace, and Fib Extend tool buttons', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: false,
				activeFibTool: null,
				isDrawingFib: false
			}
		});

		expect(screen.getByRole('button', { name: 'Elliott Wave' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Toggle Fib Retrace drawing/i })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Toggle Fib Extend drawing/i })).toBeInTheDocument();
	});

	it('opens dropdown menu and triggers onSelectWaveDegree when Cycle Degree is selected', async () => {
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

		const waveBtn = screen.getByRole('button', { name: 'Elliott Wave' });
		await fireEvent.click(waveBtn);

		const cycleOption = await screen.findByText('Cycle Degree');
		await fireEvent.click(cycleOption);

		expect(onSelectWaveDegree).toHaveBeenCalledWith('cycle');
	});

	it('opens dropdown menu and triggers onSelectWaveDegree when Primary Degree is selected', async () => {
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

		const waveBtn = screen.getByRole('button', { name: 'Elliott Wave' });
		await fireEvent.click(waveBtn);

		const primaryOption = await screen.findByText('Primary Degree');
		await fireEvent.click(primaryOption);

		expect(onSelectWaveDegree).toHaveBeenCalledWith('primary');
	});

	it('highlights Elliott Wave button when isDrawingWave is true', () => {
		render(DrawingToolbar, {
			props: {
				activeWaveDegree: 'cycle',
				isDrawingWave: true,
				activeFibTool: null,
				isDrawingFib: false
			}
		});

		const waveBtn = screen.getByRole('button', { name: 'Elliott Wave' });
		expect(waveBtn.className).toContain('bg-primary');
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
});
