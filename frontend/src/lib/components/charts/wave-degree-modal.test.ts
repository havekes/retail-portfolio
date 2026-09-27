import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import WaveDegreeModal from './wave-degree-modal.svelte';
import { ALL_WAVE_DEGREES, WAVE_DEGREE_LABELS } from '$lib/utils/finance/elliott-wave';

describe('WaveDegreeModal', () => {
	it('renders all 9 wave degree options', () => {
		render(WaveDegreeModal, {
			open: true,
			currentDegree: 'cycle'
		});

		for (const deg of ALL_WAVE_DEGREES) {
			expect(screen.getByTestId(`degree-option-${deg}`)).toBeInTheDocument();
			expect(screen.getByText(WAVE_DEGREE_LABELS[deg])).toBeInTheDocument();
		}
	});

	it('selects a new degree and saves on clicking Save Degree', async () => {
		const onSave = vi.fn();
		render(WaveDegreeModal, {
			open: true,
			currentDegree: 'cycle',
			waveId: 'test-wave-1',
			onSave
		});

		const primaryOption = screen.getByTestId('degree-option-primary');
		await fireEvent.click(primaryOption);

		const saveBtn = screen.getByTestId('save-degree-btn');
		await fireEvent.click(saveBtn);

		expect(onSave).toHaveBeenCalledWith('primary', 'test-wave-1');
	});

	it('closes on cancel without saving', async () => {
		const onSave = vi.fn();
		const onClose = vi.fn();
		render(WaveDegreeModal, {
			open: true,
			currentDegree: 'cycle',
			onSave,
			onClose
		});

		const cancelBtn = screen.getByTestId('cancel-degree-btn');
		await fireEvent.click(cancelBtn);

		expect(onSave).not.toHaveBeenCalled();
		expect(onClose).toHaveBeenCalled();
	});
});
