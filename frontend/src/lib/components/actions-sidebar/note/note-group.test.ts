import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import NoteGroup from './note-group.svelte';
import { ApiError } from '$lib/api/apiClient';
import type { SecurityNote, SecurityNoteSummary } from '$lib/api/notesService';

// Mock every API surface the group and its dialogs touch so no test ever
// performs a real network request.
vi.mock('$lib/api/notesService', () => ({
	notesService: {
		getNotes: vi.fn(),
		createNote: vi.fn(),
		updateNote: vi.fn(),
		deleteNote: vi.fn(),
		getLatestSummary: vi.fn()
	}
}));

import { notesService } from '$lib/api/notesService';

const persistedSummary = {
	summary: 'Persisted summary',
	generated_at: '2026-09-01T12:00:00Z'
};

const secondNote: SecurityNote = {
	id: 3,
	security_id: 'sec-123',
	user_id: 'user-1',
	summary: 'Second note summary.',
	content: 'Second note',
	created_at: '2026-08-20T12:00:00Z',
	updated_at: '2026-08-20T12:00:00Z'
};

const mockNote: SecurityNote = {
	id: 1,
	security_id: 'sec-123',
	user_id: 'user-1',
	summary: 'AI sentence about the note.',
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
	return render(NoteGroup, {
		props: {
			securityId: 'sec-123',
			expanded,
			// Tiny poll window so the regeneration tests don't need fake timers.
			pollIntervalMs: 1,
			maxPollAttempts: 3
		}
	});
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
		vi.mocked(notesService.getLatestSummary).mockResolvedValue(persistedSummary);
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

			const updatedNote = { ...mockNote, content: 'Updated content' };
			vi.mocked(notesService.updateNote).mockResolvedValue(updatedNote);
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			await waitFor(() =>
				expect(notesService.updateNote).toHaveBeenCalledWith('sec-123', mockNote.id, {
					content: 'Updated content'
				})
			);

			// Save switches back to view mode and shows the saved content immediately
			await waitFor(() => expect(screen.getByText('View note')).toBeInTheDocument());
			await waitFor(() => expect(screen.getByText('Updated content')).toBeInTheDocument());
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

	describe('AI summary block', () => {
		beforeEach(() => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote, secondNote],
				total: 2,
				offset: 0,
				limit: 10
			});
		});

		it('renders the persisted summary above the note list', async () => {
			renderGroup(true);

			const summary = await screen.findByText('Persisted summary');
			const item = await screen.findByText('A note from the API');

			expect(item.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
		});

		it('shows a pending state when no summary has been generated yet', async () => {
			vi.mocked(notesService.getLatestSummary).mockResolvedValue({
				summary: null,
				generated_at: null
			});
			renderGroup(true);

			expect(await screen.findByText(/summary pending/i)).toBeInTheDocument();
			expect(screen.queryByText('Try again')).not.toBeInTheDocument();
		});

		it('omits the block and never fetches a summary when there are no notes', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [],
				total: 0,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			expect(await screen.findByText('No notes yet')).toBeInTheDocument();
			expect(screen.queryByText('AI summary')).not.toBeInTheDocument();
			expect(screen.queryByText(/summary pending/i)).not.toBeInTheDocument();
			expect(notesService.getLatestSummary).not.toHaveBeenCalled();
		});

		it('re-fetches and shows the updated summary after a note is created', async () => {
			vi.mocked(notesService.getLatestSummary)
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValue({ summary: 'New summary', generated_at: 't1' });
			renderGroup(true);
			await screen.findByText('Old summary');

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');
			await fireEvent.input(textarea, { target: { value: 'Another note' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			await waitFor(() => expect(screen.getByText('New summary')).toBeInTheDocument());
			expect(screen.queryByText('Old summary')).not.toBeInTheDocument();
		});

		it('re-fetches and shows the updated summary after a note is updated', async () => {
			vi.mocked(notesService.getLatestSummary)
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValue({ summary: 'New summary', generated_at: 't1' });
			renderGroup(true);
			await screen.findByText('Old summary');

			await fireEvent.click(await screen.findByText('A note from the API'));
			await waitFor(() => expect(screen.getByText('View note')).toBeInTheDocument());
			await fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
			const editArea = screen.getByPlaceholderText('Enter note content...');
			await fireEvent.input(editArea, { target: { value: 'Updated content' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			await waitFor(() => expect(screen.getByText('New summary')).toBeInTheDocument());
		});

		it('re-fetches and shows the updated summary after a note is deleted', async () => {
			vi.mocked(notesService.getLatestSummary)
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValueOnce({ summary: 'Old summary', generated_at: 't0' })
				.mockResolvedValue({ summary: 'New summary', generated_at: 't1' });
			renderGroup(true);
			await screen.findByText('Old summary');

			await fireEvent.click(screen.getAllByTitle('Delete note')[0]);
			await waitFor(() => expect(screen.getByText('Delete Note')).toBeInTheDocument());
			await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

			await waitFor(() =>
				expect(notesService.deleteNote).toHaveBeenCalledWith('sec-123', mockNote.id)
			);
			await waitFor(() => expect(screen.getByText('New summary')).toBeInTheDocument());
		});

		it('does not refresh the summary after deleting the last note', async () => {
			vi.mocked(notesService.getNotes)
				.mockResolvedValueOnce({ items: [mockNote], total: 1, offset: 0, limit: 10 })
				.mockResolvedValue({ items: [], total: 0, offset: 0, limit: 10 });
			renderGroup(true);

			await screen.findByText('Persisted summary');
			await fireEvent.click(screen.getByTitle('Delete note'));
			await waitFor(() => expect(screen.getByText('Delete Note')).toBeInTheDocument());
			await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

			await waitFor(() =>
				expect(notesService.deleteNote).toHaveBeenCalledWith('sec-123', mockNote.id)
			);
			await waitFor(() => expect(screen.getByText('No notes yet')).toBeInTheDocument());
			// The block unmounted with the last note: no pointless regeneration poll.
			expect(notesService.getLatestSummary).toHaveBeenCalledTimes(1);
		});

		it('shows the summary once regeneration lands after a pending state', async () => {
			vi.mocked(notesService.getLatestSummary)
				.mockResolvedValueOnce({ summary: null, generated_at: null })
				.mockResolvedValueOnce({ summary: null, generated_at: null })
				.mockResolvedValue({ summary: 'Brand new summary', generated_at: 't1' });
			renderGroup(true);
			await screen.findByText(/summary pending/i);

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');
			await fireEvent.input(textarea, { target: { value: 'Another note' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			expect(await screen.findByText('Brand new summary')).toBeInTheDocument();
		});

		it('announces regeneration when no summary is persisted yet', async () => {
			let resolveRefresh!: (value: SecurityNoteSummary) => void;
			vi.mocked(notesService.getLatestSummary)
				.mockResolvedValueOnce({ summary: null, generated_at: null })
				.mockImplementationOnce(
					() =>
						new Promise<SecurityNoteSummary>((resolve) => {
							resolveRefresh = resolve;
						})
				)
				.mockResolvedValue({ summary: 'Fresh summary', generated_at: 't1' });
			renderGroup(true);
			await screen.findByText(/summary pending/i);

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');
			await fireEvent.input(textarea, { target: { value: 'Another note' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			// The refresh is still in flight with nothing persisted yet: show
			// progress, not the static pending copy.
			expect(await screen.findByText(/generating summary/i)).toBeInTheDocument();

			resolveRefresh({ summary: 'Fresh summary', generated_at: 't1' });
			expect(await screen.findByText('Fresh summary')).toBeInTheDocument();
		});

		it('stays in the error state when a retry fails again', async () => {
			vi.mocked(notesService.getLatestSummary)
				.mockRejectedValueOnce(new ApiError(500, 'summary unavailable'))
				.mockRejectedValueOnce(new ApiError(500, 'still unavailable'));
			renderGroup(true);

			expect(await screen.findByText('summary unavailable')).toBeInTheDocument();
			await fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

			expect(await screen.findByText('still unavailable')).toBeInTheDocument();
			expect(screen.getByText('Try again')).toBeInTheDocument();
		});

		it('recovers from the error state when a retry succeeds', async () => {
			vi.mocked(notesService.getLatestSummary).mockRejectedValueOnce(
				new ApiError(500, 'summary unavailable')
			);
			renderGroup(true);

			expect(await screen.findByText('summary unavailable')).toBeInTheDocument();
			await fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

			expect(await screen.findByText('Persisted summary')).toBeInTheDocument();
			expect(screen.queryByText('summary unavailable')).not.toBeInTheDocument();
		});

		it('wraps non-API errors in the generic load message', async () => {
			vi.mocked(notesService.getLatestSummary).mockRejectedValue(new TypeError('Failed to fetch'));
			renderGroup(true);

			expect(await screen.findByText('Failed to load summary')).toBeInTheDocument();
			expect(screen.queryByText('Failed to fetch')).not.toBeInTheDocument();
		});
	});

	describe('per-note AI summaries', () => {
		beforeEach(() => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote],
				total: 1,
				offset: 0,
				limit: 10
			});
		});

		it('renders the sentence summary beneath the note preview', async () => {
			renderGroup(true);

			expect(await screen.findByText('AI sentence about the note.')).toBeInTheDocument();
			expect(screen.queryByText('Summarizing…')).not.toBeInTheDocument();
		});

		it('shows a muted pending fallback while the summary is null', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [{ ...mockNote, id: 9, summary: null }],
				total: 1,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			expect(await screen.findByText('Summarizing…')).toBeInTheDocument();
		});

		it('polls the list until a freshly created note carries its summary', async () => {
			const withoutSummary: SecurityNote = { ...mockNote, id: 42, summary: null };
			vi.mocked(notesService.getNotes)
				// initial mount
				.mockResolvedValueOnce({ items: [mockNote], total: 1, offset: 0, limit: 10 })
				// first refetch after creating the note: summary not generated yet
				.mockResolvedValueOnce({ items: [withoutSummary], total: 1, offset: 0, limit: 10 })
				// a later poll picks up the generated sentence
				.mockResolvedValue({
					items: [{ ...withoutSummary, summary: 'Fresh sentence.' }],
					total: 1,
					offset: 0,
					limit: 10
				});
			renderGroup(true);
			await screen.findByText('AI sentence about the note.');

			await fireEvent.keyDown(window, { key: 'n' });
			const textarea = await screen.findByPlaceholderText('Enter your note here...');
			await fireEvent.input(textarea, { target: { value: 'Another note' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Save note' }));

			expect(await screen.findByText('Fresh sentence.')).toBeInTheDocument();
		});
	});

	describe('delete confirmation stacking', () => {
		it('raises the confirmation above an open note dialog', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote],
				total: 1,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			await fireEvent.click(await screen.findByText('A note from the API'));
			await waitFor(() => expect(screen.getByText('View note')).toBeInTheDocument());

			await fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

			const confirmTitle = await screen.findByText('Delete Note');
			const confirmContent = confirmTitle.closest('[data-slot="dialog-content"]');
			expect(confirmContent).not.toBeNull();
			// Strictly above the z-50 note dialog so it is clickable.
			expect(confirmContent?.className).toContain('z-[60]');
		});

		it('keeps the delete confirmation above the list-only quick delete path', async () => {
			vi.mocked(notesService.getNotes).mockResolvedValue({
				items: [mockNote],
				total: 1,
				offset: 0,
				limit: 10
			});
			renderGroup(true);

			await fireEvent.click(await screen.findByTitle('Delete note'));

			const confirmTitle = await screen.findByText('Delete Note');
			const confirmContent = confirmTitle.closest('[data-slot="dialog-content"]');
			expect(confirmContent?.className).toContain('z-[60]');
		});
	});
});
