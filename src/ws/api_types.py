from enum import StrEnum

from pydantic import BaseModel

from src.account.api_types import AccountId, AccountTotals


class WsEventType(StrEnum):
    ACCOUNT_SYNC_STARTED = "sync_started"
    ACCOUNT_SYNC_FINISHED = "sync_finished"
    ACCOUNT_SYNC_FAILED = "sync_failed"
    ACCOUNT_TOTALS_UPDATED = "account_totals_updated"


class WsMessage(BaseModel):
    type: WsEventType


class AccountSyncMessage(WsMessage):
    account_id: AccountId


class AccountTotalsUpdatedMessage(WsMessage):
    type: WsEventType = WsEventType.ACCOUNT_TOTALS_UPDATED
    account_id: AccountId
    totals: AccountTotals
