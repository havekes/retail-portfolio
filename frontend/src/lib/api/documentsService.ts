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

		return await this.postFormData<DocumentUploadResponse>(
			`/market/securities/${securityId}/documents`,
			formData
		);
	}

	async downloadDocument(securityId: string, documentId: number): Promise<Blob> {
		return await this.getBlob(
			`/market/securities/${securityId}/documents/${documentId}/download`
		);
	}

	async deleteDocument(securityId: string, documentId: number): Promise<void> {
		return await this.delete(`/market/securities/${securityId}/documents/${documentId}`);
	}
}

export const documentsService = new DocumentsService();
