import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NotesService } from './notesService';

// All requests are fetch-mocked: no test here performs a real network request.
describe('NotesService', () => {
	let client: NotesService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new NotesService();
	});

	it('updates a note with PUT (backend route verb)', async () => {
		const mockResponse = {
			id: 5,
			security_id: 'sec-1',
			user_id: 'user-1',
			title: 'Title',
			summary: 'A sentence.',
			content: 'Updated content',
			created_at: '2026-09-01T12:00:00Z',
			updated_at: '2026-09-02T12:00:00Z'
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.updateNote('sec-1', 5, { content: 'Updated content' });

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/notes/5'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify({ content: 'Updated content' })
			})
		);
	});

	it('parses the nullable summary returned by the list endpoint', async () => {
		const noteWithoutSummary = {
			id: 7,
			security_id: 'sec-1',
			user_id: 'user-1',
			content: 'Body',
			summary: null,
			created_at: '2026-09-01T12:00:00Z',
			updated_at: '2026-09-01T12:00:00Z'
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ items: [noteWithoutSummary], total: 1, offset: 0, limit: 10 })
		} as Response);

		const result = await client.getNotes('sec-1');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/market/securities/sec-1/notes'),
			expect.objectContaining({ method: 'GET' })
		);
		expect(result.items[0].summary).toBeNull();
	});
});
