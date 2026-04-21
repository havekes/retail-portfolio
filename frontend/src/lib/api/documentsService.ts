import { ApiClient } from './apiClient';

export interface SecurityDocument {
	id: number;
	security_id: string;
	user_id: string;
	filename: string;
	file_path: string;
	file_size: number;
	file_type: string;
	created_at: string;
}

export interface DocumentUploadResponse {
	id: number;
	filename: string;
	file_size: number;
	file_type: string;
	created_at: string;
}

export class DocumentsService extends ApiClient {
	async getDocuments(securityId: string): Promise<SecurityDocument[]> {
		return await this.get<SecurityDocument[]>(`/market/securities/${securityId}/documents`);
	}

	async uploadDocument(securityId: string, file: File): Promise<DocumentUploadResponse> {
		const formData = new FormData();
		formData.append('file', file);

		const response = await fetch(`${this.baseUrl}/market/securities/${securityId}/documents`, {
			method: 'POST',
			credentials: 'include',
			body: formData
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({ detail: response.statusText }));
			throw new Error(errorData.detail || 'Failed to upload document');
		}

		return response.json();
	}

	async downloadDocument(securityId: string, documentId: number): Promise<Blob> {
		const response = await fetch(
			`${this.baseUrl}/market/securities/${securityId}/documents/${documentId}/download`,
			{
				method: 'GET',
				credentials: 'include'
			}
		);

		if (!response.ok) {
			throw new Error('Failed to download document');
		}

		return response.blob();
	}

	async deleteDocument(securityId: string, documentId: number): Promise<void> {
		return await this.delete(`/market/securities/${securityId}/documents/${documentId}`);
	}
}

export const documentsService = new DocumentsService();
