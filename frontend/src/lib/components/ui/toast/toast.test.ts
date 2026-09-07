import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import { ToastState, toast } from './toast.svelte.js';
import Toaster from './toaster.svelte';

describe('ToastState', () => {
	let customToast: ToastState;

	beforeEach(() => {
		vi.useFakeTimers();
		customToast = new ToastState();
		toast.clear();
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.useRealTimers();
		customToast.clear();
		toast.clear();
	});

	it('adds a toast with default options', () => {
		const id = customToast.add('Test message');
		expect(id).toBeDefined();
		expect(customToast.toasts).toHaveLength(1);
		expect(customToast.toasts[0]).toEqual({
			id,
			message: 'Test message',
			type: 'info',
			duration: 4000
		});
	});

	it('adds toasts using convenience methods (success, error, info, warning)', () => {
		customToast.success('Success message');
		customToast.error('Error message');
		customToast.info('Info message');
		customToast.warning('Warning message');

		expect(customToast.toasts).toHaveLength(4);
		expect(customToast.toasts[0].type).toBe('success');
		expect(customToast.toasts[0].message).toBe('Success message');
		expect(customToast.toasts[1].type).toBe('error');
		expect(customToast.toasts[1].message).toBe('Error message');
		expect(customToast.toasts[2].type).toBe('info');
		expect(customToast.toasts[2].message).toBe('Info message');
		expect(customToast.toasts[3].type).toBe('warning');
		expect(customToast.toasts[3].message).toBe('Warning message');
	});

	it('auto-removes toasts when duration expires', () => {
		customToast.add('Expiring soon', { duration: 1000 });
		expect(customToast.toasts).toHaveLength(1);

		vi.advanceTimersByTime(999);
		expect(customToast.toasts).toHaveLength(1);

		vi.advanceTimersByTime(1);
		expect(customToast.toasts).toHaveLength(0);
	});

	it('does not auto-remove when duration is 0', () => {
		customToast.add('Persistent toast', { duration: 0 });
		expect(customToast.toasts).toHaveLength(1);

		vi.advanceTimersByTime(10000);
		expect(customToast.toasts).toHaveLength(1);
	});

	it('removes a specific toast by id and clears its timer', () => {
		const id1 = customToast.add('First');
		const id2 = customToast.add('Second');
		expect(customToast.toasts).toHaveLength(2);

		customToast.remove(id1);
		expect(customToast.toasts).toHaveLength(1);
		expect(customToast.toasts[0].id).toBe(id2);
	});

	it('clears all toasts and timers on clear()', () => {
		customToast.add('First');
		customToast.add('Second');
		expect(customToast.toasts).toHaveLength(2);

		customToast.clear();
		expect(customToast.toasts).toHaveLength(0);
	});
});

describe('Toaster Component', () => {
	beforeEach(() => {
		toast.clear();
	});

	afterEach(() => {
		toast.clear();
	});

	it('renders toasts and dismisses on close button click', async () => {
		render(Toaster);

		toast.success('Snapshot saved successfully');
		toast.error('Failed to save snapshot');

		expect(await screen.findByText('Snapshot saved successfully')).toBeInTheDocument();
		expect(screen.getByText('Failed to save snapshot')).toBeInTheDocument();

		const successToast = screen.getByTestId('toast-success');
		const errorToast = screen.getByTestId('toast-error');

		expect(successToast).toHaveAttribute('role', 'status');
		expect(errorToast).toHaveAttribute('role', 'alert');

		const dismissButtons = screen.getAllByRole('button', { name: 'Dismiss toast' });
		expect(dismissButtons).toHaveLength(2);

		await fireEvent.click(dismissButtons[0]);
		expect(screen.queryByText('Snapshot saved successfully')).not.toBeInTheDocument();
		expect(screen.getByText('Failed to save snapshot')).toBeInTheDocument();
	});
});
