import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import NoteGroup from './note-group.svelte';
import type { SecurityNote } from '$lib/api/notesService';

// Mock every API surface the group and its dialogs touch so no test ever
// performs a real network request.
vi.mock('$lib/api/notesService', () => ({
	notesService: {
		getNotes: vi.fn(),
		createNote: vi.fn(),
		updateNote: vi.fn(),
		deleteNote: vi.fn()
	}
}));

import { notesService } from '$lib/api/notesService';

const mockNote: SecurityNote = {
	id: 1,
	security_id: 'sec-123',
	user_id: 'user-1',
	content: 'A note from the API',
	created_at: '2026-09-01T12:00:00Z',
	updated_at: '2026-09-01T12:00:00Z'
};

const createdNote: SecurityNote = {
	...mockNote,
	id: 2,
	content: 'Hello note'
};

function renderGroup(expanded = false) {
	return render(NoteGroup, { props: { securityId: 'sec-123', expanded } });
}

const dialogTitle = () => screen.queryByText('Add note');
const contentTextarea = () => document.getElementById('note-content');

describe('NoteGroup', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(notesService.getNotes).mockResolvedValue({
			items: [],
			total: 0,
			offset: 0,
			limit: 10
		});
		vi.mocked(notesService.createNote).mockResolvedValue(createdNote);
		vi.mocked(notesService.updateNote).mockResolvedValue(createdNote);
		vi.mocked(notesService.deleteNote).mockResolvedValue(undefined);
	});

	describe('n shortcut', () => {
		it('opens the Add note dialog on "n"', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n' });

			await waitFor(() => expect(dialogTitle()).toBeInTheDocument());
			expect(contentTextarea()).toBeInTheDocument();
		});

		it('opens the Add note dialog on "N"', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'N' });

			await waitFor(() => expect(dialogTitle()).toBeInTheDocument());
		});

		it('ignores "n" when a modifier key is held', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n', ctrlKey: true });
			await fireEvent.keyDown(window, { key: 'n', metaKey: true });
			await fireEvent.keyDown(window, { key: 'n', altKey: true });

			expect(dialogTitle()).not.toBeInTheDocument();
		});

		it('ignores "n" dispatched from a typing surface', async () => {
			renderGroup();

			const targets = [
				document.createElement('input'),
				document.createElement('textarea'),
				document.createElement('select'),
				document.createElement('div')
			];
			const [input, textarea, select, editable] = targets;
			editable.setAttribute('contenteditable', 'true');
			document.body.append(...targets);

			for (const target of targets) {
				await fireEvent.keyDown(target, { key: 'n' });
			}

			expect(dialogTitle()).not.toBeInTheDocument();
			input.remove();
			textarea.remove();
			select.remove();
			editable.remove();
		});

		it('does not stack a second dialog when one is already open', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n' });
			await waitFor(() => expect(contentTextarea()).toBeInTheDocument());

			await fireEvent.keyDown(window, { key: 'n' });

			expect(screen.getAllByText('Add note')).toHaveLength(1);
			expect(
				document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]')
			).toHaveLength(1);
		});

		it('places focus in the content textarea when the dialog opens', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n' });

			await waitFor(() => expect(contentTextarea()).toHaveFocus());
		});
	});

	describe('existing note behaviour', () => {
		it('renders the note list and opens the view dialog on click', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote],
				total: 1,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			const item = await screen.findByText('A note from the API');
			await fireEvent.click(item);

			await waitFor(() => expect(screen.getByText('View note')).toBeInTheDocument());
		});

		it('creates a note with trimmed content and closes the dialog', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');

			await fireEvent.input(textarea, { target: { value: '  Hello note  ' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			await waitFor(() =>
				expect(notesService.createNote).toHaveBeenCalledWith('sec-123', {
					content: 'Hello note'
				})
			);
			await waitFor(() => expect(dialogTitle()).not.toBeInTheDocument());
		});

		it('saves on Enter in the content textarea', async () => {
			renderGroup();

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');

			await fireEvent.input(textarea, { target: { value: 'Entered note' } });
			await fireEvent.keyDown(textarea, { key: 'Enter' });

			await waitFor(() =>
				expect(notesService.createNote).toHaveBeenCalledWith('sec-123', {
					content: 'Entered note'
				})
			);
		});

		it('updates a note from the view dialog', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote],
				total: 1,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			await fireEvent.click(await screen.findByText('A note from the API'));
			await waitFor(() => expect(screen.getByText('View note')).toBeInTheDocument());

			await fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
			const editArea = screen.getByPlaceholderText('Enter note content...');
			await fireEvent.input(editArea, { target: { value: 'Updated content' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			await waitFor(() =>
				expect(notesService.updateNote).toHaveBeenCalledWith('sec-123', mockNote.id, {
					content: 'Updated content'
				})
			);
		});

		it('deletes a note after confirmation', async () => {
			vi.mocked(notesService.getNotes)
				.mockResolvedValueOnce({ items: [mockNote], total: 1, offset: 0, limit: 10 })
				.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 10 });
			renderGroup(true);

			await screen.findByText('A note from the API');
			await fireEvent.click(screen.getByTitle('Delete note'));

			await waitFor(() => expect(screen.getByText('Delete Note')).toBeInTheDocument());
			await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

			await waitFor(() =>
				expect(notesService.deleteNote).toHaveBeenCalledWith('sec-123', mockNote.id)
			);
		});
	});
});
