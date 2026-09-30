import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import RenameAccountModal from './rename-account-modal.svelte';

describe('RenameAccountModal', () => {
	it('renders dialog when open is true and pre-fills current account name', () => {
		render(RenameAccountModal, {
			props: {
				open: true,
				currentName: 'My Savings Account'
			}
		});

		expect(screen.getByRole('heading', { name: 'Rename account' })).toBeInTheDocument();
		const input = screen.getByLabelText('Account Name') as HTMLInputElement;
		expect(input).toBeInTheDocument();
		expect(input.value).toBe('My Savings Account');
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
	});

	it('does not render dialog content when open is false', () => {
		render(RenameAccountModal, {
			props: {
				open: false,
				currentName: 'My Savings Account'
			}
		});

		expect(screen.queryByRole('heading', { name: 'Rename account' })).not.toBeInTheDocument();
	});

	it('invokes oncancel and closes modal when Cancel is clicked', async () => {
		const onCancel = vi.fn();
		render(RenameAccountModal, {
			props: {
				open: true,
				currentName: 'My Savings Account',
				oncancel: onCancel
			}
		});

		const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
		await fireEvent.click(cancelBtn);

		expect(onCancel).toHaveBeenCalledTimes(1);
	});

	it('shows error if input is cleared and save is attempted', async () => {
		const onSave = vi.fn();
		render(RenameAccountModal, {
			props: {
				open: true,
				currentName: 'My Savings Account',
				onsave: onSave
			}
		});

		const input = screen.getByLabelText('Account Name');
		await fireEvent.input(input, { target: { value: '   ' } });

		// Even if button is disabled, form submit can be triggered
		const form = input.closest('form')!;
		await fireEvent.submit(form);

		expect(screen.getByText('Account name is required.')).toBeInTheDocument();
		expect(onSave).not.toHaveBeenCalled();
	});

	it('invokes onsave with trimmed name and closes modal on valid submit', async () => {
		const onSave = vi.fn().mockResolvedValue(undefined);
		render(RenameAccountModal, {
			props: {
				open: true,
				currentName: 'My Savings Account',
				onsave: onSave
			}
		});

		const input = screen.getByLabelText('Account Name');
		await fireEvent.input(input, { target: { value: 'New Account Name  ' } });

		const saveBtn = screen.getByRole('button', { name: 'Save' });
		await fireEvent.click(saveBtn);

		await waitFor(() => {
			expect(onSave).toHaveBeenCalledWith('New Account Name');
		});
	});

	it('displays error message when onsave rejects and keeps modal open', async () => {
		const onSave = vi.fn().mockRejectedValue(new Error('Server error updating name'));
		render(RenameAccountModal, {
			props: {
				open: true,
				currentName: 'My Savings Account',
				onsave: onSave
			}
		});

		const input = screen.getByLabelText('Account Name');
		await fireEvent.input(input, { target: { value: 'New Account Name' } });

		const saveBtn = screen.getByRole('button', { name: 'Save' });
		await fireEvent.click(saveBtn);

		await waitFor(() => {
			expect(screen.getByText('Server error updating name')).toBeInTheDocument();
		});
		expect(screen.getByRole('heading', { name: 'Rename account' })).toBeInTheDocument();
	});
});
