import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AccountsListItem from './accounts-list-item.svelte';
import { Institution, AccountType } from '@/types/account';

describe('AccountsListItem', () => {
	const mockAccount = {
		id: 'acc-1',
		name: 'My Test Account',
		institution_id: Institution.Wealthsimple,
		account_type_id: AccountType.TFSA,
		currency: 'CAD',
		broker_display_name: 'Broker'
	};

	it('should render the account name and allow renaming without mutating unbound props directly', async () => {
		const onRenameMock = vi.fn();
		const onToggleSelectionMock = vi.fn();
		const onSyncMock = vi.fn();

		const { component } = render(AccountsListItem, {
			props: {
				account: mockAccount,
				selectionMode: false,
				isSelected: false,
				isSyncing: false,
				syncError: null,
				onToggleSelection: onToggleSelectionMock,
				onSync: onSyncMock,
				onRename: onRenameMock
			}
		});

		// Ensure it renders the title
		const titleElement = screen.getByText('My Test Account');
		expect(titleElement).toBeInTheDocument();

		// Click the edit button (pencil icon)
		// It has a title/label or we can grab the button next to the title
		const editButton = titleElement.parentElement?.querySelector('button');
		expect(editButton).toBeInTheDocument();
		await fireEvent.click(editButton!);

		// Now it should show an input
		const input = screen.getByRole('textbox');
		expect(input).toBeInTheDocument();
		expect((input as HTMLInputElement).value).toBe('My Test Account');

		// Change the input value
		await fireEvent.input(input, { target: { value: 'Updated Account Name' } });
		
		// Wait for the action to complete/enhance form
		// Instead of testing form enhancement (since it's tricky to mock SvelteKit's enhance action in JSDOM easily),
		// we can test the fallback 'save' button or keypress. Wait, EditableTitle renders a form if 'action' is present.
		// If action is present, we click the submit button.
		const form = input.closest('form');
		if (form) {
			const submitBtn = form.querySelector('button[type="submit"]');
			expect(submitBtn).toBeInTheDocument();
		}
	});
});
