import { getSecurityClient, type SecurityClient } from '$lib/api/securityClient';
import type {
	TwoFactorStatusResponse,
	PasskeyResponse,
	TotpSetupResponse,
	TotpActivateResponse,
	TotpDisableRequest,
	MessageResponse
} from '$lib/api/types/security';
import { startRegistration, browserSupportsWebAuthn } from '@simplewebauthn/browser';
import { getContext, setContext } from 'svelte';

export class SecurityService {
	status = $state<TwoFactorStatusResponse | null>(null);
	passkeys = $state<PasskeyResponse[]>([]);
	isLoading = $state(false);
	error = $state<string | null>(null);
	private client: SecurityClient;

	constructor(customFetch?: typeof fetch) {
		this.client = getSecurityClient(customFetch);
	}

	async loadStatus(token?: string | null): Promise<TwoFactorStatusResponse | null> {
		this.isLoading = true;
		this.error = null;
		try {
			this.status = await this.client.get2FaStatus(token);
			return this.status;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to load 2FA status';
			console.error(err);
			return null;
		} finally {
			this.isLoading = false;
		}
	}

	async loadPasskeys(token?: string | null): Promise<PasskeyResponse[]> {
		this.isLoading = true;
		this.error = null;
		try {
			this.passkeys = await this.client.getPasskeys(token);
			return this.passkeys;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to load passkeys';
			console.error(err);
			return [];
		} finally {
			this.isLoading = false;
		}
	}

	async setupTotp(token?: string | null): Promise<TotpSetupResponse> {
		this.isLoading = true;
		this.error = null;
		try {
			return await this.client.setupTotp(token);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to initialize TOTP setup';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async activateTotp(code: string, token?: string | null): Promise<TotpActivateResponse> {
		this.isLoading = true;
		this.error = null;
		try {
			const res = await this.client.activateTotp(code, token);
			this.status = {
				totp_enabled: true,
				recovery_codes_remaining: res.recovery_codes?.length ?? 8
			};
			return res;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to activate 2FA';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async disableTotp(
		request: TotpDisableRequest = {},
		token?: string | null
	): Promise<MessageResponse> {
		this.isLoading = true;
		this.error = null;
		try {
			const res = await this.client.disableTotp(request, token);
			this.status = {
				totp_enabled: false,
				recovery_codes_remaining: 0
			};
			return res;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to disable 2FA';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async regenerateRecoveryCodes(token?: string | null): Promise<string[]> {
		this.isLoading = true;
		this.error = null;
		try {
			const res = await this.client.regenerateRecoveryCodes(token);
			if (this.status) {
				this.status = {
					...this.status,
					totp_enabled: true,
					recovery_codes_remaining: res.recovery_codes.length
				};
			}
			return res.recovery_codes;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to regenerate recovery codes';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async registerPasskey(name: string = 'Passkey', token?: string | null): Promise<PasskeyResponse> {
		this.isLoading = true;
		this.error = null;
		try {
			if (!browserSupportsWebAuthn()) {
				throw new Error('WebAuthn is not supported on this device or browser');
			}
			const options = await this.client.getPasskeyRegistrationOptions(token);
			let credential;
			try {
				credential = await startRegistration({ optionsJSON: options });
			} catch (authErr: unknown) {
				const e = authErr as { name?: string; message?: string };
				if (e?.name === 'NotAllowedError') {
					throw new Error('Passkey registration was cancelled or timed out', { cause: authErr });
				}
				if (e?.name === 'InvalidStateError') {
					throw new Error('This passkey is already registered', { cause: authErr });
				}
				throw new Error(e?.message || 'Failed to complete WebAuthn ceremony', { cause: authErr });
			}
			const newPasskey = await this.client.verifyPasskeyRegistration(
				{ credential, name: name.trim() || 'Passkey' },
				token
			);
			this.passkeys = [...this.passkeys, newPasskey];
			return newPasskey;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to register passkey';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async renamePasskey(
		passkeyId: string,
		name: string,
		token?: string | null
	): Promise<PasskeyResponse> {
		this.isLoading = true;
		this.error = null;
		try {
			const updated = await this.client.renamePasskey(passkeyId, name.trim(), token);
			this.passkeys = this.passkeys.map((pk) => (pk.id === passkeyId ? updated : pk));
			return updated;
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to rename passkey';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}

	async deletePasskey(passkeyId: string, token?: string | null): Promise<void> {
		this.isLoading = true;
		this.error = null;
		try {
			await this.client.deletePasskey(passkeyId, token);
			this.passkeys = this.passkeys.filter((pk) => pk.id !== passkeyId);
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			this.error = message || 'Failed to delete passkey';
			throw err;
		} finally {
			this.isLoading = false;
		}
	}
}

const SECURITY_SERVICE_KEY = Symbol('security-service');
let defaultService: SecurityService | null = null;

export function setSecurityService(initialData?: {
	status?: TwoFactorStatusResponse | null;
	passkeys?: PasskeyResponse[];
}) {
	const service = new SecurityService();
	if (initialData?.status !== undefined) service.status = initialData.status;
	if (initialData?.passkeys !== undefined) service.passkeys = initialData.passkeys;
	defaultService = service;
	try {
		setContext(SECURITY_SERVICE_KEY, service);
	} catch {
		// setContext called outside component hierarchy
	}
	return service;
}

export function getSecurityService(customFetch?: typeof fetch) {
	if (customFetch) {
		return new SecurityService(customFetch);
	}
	try {
		const ctx = getContext<SecurityService>(SECURITY_SERVICE_KEY);
		if (ctx) return ctx;
	} catch {
		// getContext called outside component hierarchy
	}
	if (!defaultService) {
		defaultService = new SecurityService();
	}
	return defaultService;
}
