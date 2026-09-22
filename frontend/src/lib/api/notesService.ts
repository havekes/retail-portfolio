import { ApiClient } from './apiClient';
import type { PaginatedResponse } from '../types/pagination';

export interface SecurityNote {
	id: number;
	security_id: string;
	user_id: string;
	title?: string;
	summary?: string | null;
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

export interface SecurityNoteSummary {
	summary: string | null;
	generated_at: string | null;
}

export class NotesService extends ApiClient {
	async getNotes(securityId: string): Promise<PaginatedResponse<SecurityNote>> {
		return await this.get<PaginatedResponse<SecurityNote>>(
			`/market/securities/${securityId}/notes`
		);
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
		return await this.put<SecurityNote, SecurityNoteUpdateRequest>(
			`/market/securities/${securityId}/notes/${noteId}`,
			request
		);
	}

	async deleteNote(securityId: string, noteId: number): Promise<void> {
		return await this.delete(`/market/securities/${securityId}/notes/${noteId}`);
	}

	async getLatestSummary(securityId: string): Promise<SecurityNoteSummary> {
		return await this.get<SecurityNoteSummary>(`/market/securities/${securityId}/ai/notes-summary`);
	}
}

export const notesService = new NotesService();
