import { ApiClient } from './apiClient';

export interface SecurityNote {
	id: number;
	security_id: string;
	user_id: string;
	title?: string;
	content: string;
	created_at: string;
	updated_at: string;
}

export interface SecurityNoteCreateRequest {
	content: string;
}

export interface SecurityNoteUpdateRequest {
	content: string;
}

export class NotesService extends ApiClient {
	async getNotes(securityId: string): Promise<SecurityNote[]> {
		return await this.get<SecurityNote[]>(`/market/securities/${securityId}/notes`);
	}

	async createNote(securityId: string, request: SecurityNoteCreateRequest): Promise<SecurityNote> {
		return await this.post<SecurityNote, SecurityNoteCreateRequest>(
			`/market/securities/${securityId}/notes`,
			request
		);
	}

	async updateNote(
		securityId: string,
		noteId: number,
		request: SecurityNoteUpdateRequest
	): Promise<SecurityNote> {
		return await this.patch<SecurityNote, SecurityNoteUpdateRequest>(
			`/market/securities/${securityId}/notes/${noteId}`,
			request
		);
	}

	async deleteNote(securityId: string, noteId: number): Promise<void> {
		return await this.delete(`/market/securities/${securityId}/notes/${noteId}`);
	}
}

export const notesService = new NotesService();
