export interface TwoFactorStatusResponse {
	totp_enabled: boolean;
	recovery_codes_remaining: number;
}

export interface TotpSetupResponse {
	secret: string;
	provisioning_uri: string;
}

export interface TotpActivateRequest {
	code: string;
}

export interface TotpActivateResponse {
	recovery_codes: string[];
	message: string;
}

export interface TotpDisableRequest {
	code?: string;
	password?: string;
}

export interface TotpRegenerateCodesResponse {
	recovery_codes: string[];
}

export interface PasskeyResponse {
	id: string;
	name: string;
	created_at: string;
	last_used_at?: string | null;
	transports?: string[] | null;
}

export interface PasskeyRegisterVerifyRequest {
	credential: unknown;
	name: string;
}

export interface PasskeyUpdateRequest {
	name: string;
}

export interface MessageResponse {
	message: string;
}
