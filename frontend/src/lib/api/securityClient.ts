import { ApiClient } from './apiClient';
import type {
	TwoFactorStatusResponse,
	TotpSetupResponse,
	TotpActivateRequest,
	TotpActivateResponse,
	TotpDisableRequest,
	TotpRegenerateCodesResponse,
	PasskeyResponse,
	PasskeyRegisterVerifyRequest,
	PasskeyUpdateRequest,
	MessageResponse
} from './types/security';
import type { PublicKeyCredentialCreationOptionsJSON } from '@simplewebauthn/browser';

export class SecurityClient extends ApiClient {
	async get2FaStatus(token?: string | null): Promise<TwoFactorStatusResponse> {
		return this.get<TwoFactorStatusResponse>('/auth/2fa/status', {}, token);
	}

	async setupTotp(token?: string | null): Promise<TotpSetupResponse> {
		return this.post<TotpSetupResponse, Record<string, never>>(
			'/auth/2fa/totp/setup',
			{},
			{},
			token
		);
	}

	async activateTotp(code: string, token?: string | null): Promise<TotpActivateResponse> {
		return this.post<TotpActivateResponse, TotpActivateRequest>(
			'/auth/2fa/totp/activate',
			{ code },
			{},
			token
		);
	}

	async disableTotp(
		request: TotpDisableRequest = {},
		token?: string | null
	): Promise<MessageResponse> {
		return this.post<MessageResponse, TotpDisableRequest>(
			'/auth/2fa/totp/disable',
			request,
			{},
			token
		);
	}

	async regenerateRecoveryCodes(token?: string | null): Promise<TotpRegenerateCodesResponse> {
		return this.post<TotpRegenerateCodesResponse, Record<string, never>>(
			'/auth/2fa/totp/recovery-codes/regenerate',
			{},
			{},
			token
		);
	}

	async getPasskeyRegistrationOptions(
		token?: string | null
	): Promise<PublicKeyCredentialCreationOptionsJSON> {
		return this.post<PublicKeyCredentialCreationOptionsJSON, Record<string, never>>(
			'/auth/passkey/register/options',
			{},
			{},
			token
		);
	}

	async verifyPasskeyRegistration(
		payload: PasskeyRegisterVerifyRequest,
		token?: string | null
	): Promise<PasskeyResponse> {
		return this.post<PasskeyResponse, PasskeyRegisterVerifyRequest>(
			'/auth/passkey/register/verify',
			payload,
			{},
			token
		);
	}

	async getPasskeys(token?: string | null): Promise<PasskeyResponse[]> {
		return this.get<PasskeyResponse[]>('/auth/passkeys', {}, token);
	}

	async renamePasskey(
		passkeyId: string,
		name: string,
		token?: string | null
	): Promise<PasskeyResponse> {
		return this.patch<PasskeyResponse, PasskeyUpdateRequest>(
			`/auth/passkeys/${passkeyId}`,
			{ name },
			{},
			token
		);
	}

	async deletePasskey(passkeyId: string, token?: string | null): Promise<MessageResponse> {
		return this.delete<MessageResponse>(`/auth/passkeys/${passkeyId}`, {}, token);
	}
}

export const getSecurityClient = (customFetch?: typeof fetch) => new SecurityClient(customFetch);
export const securityClient = getSecurityClient();
