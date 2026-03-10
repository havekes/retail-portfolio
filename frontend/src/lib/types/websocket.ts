export enum WsEventType {
	SYNC_STARTED = 'sync_started',
	SYNC_FINISHED = 'sync_finished',
	SYNC_FAILED = 'sync_failed'
}

export interface WsMessage {
	type: WsEventType;
}

export interface AccountSyncMessage extends WsMessage {
	account_id: string;
}
