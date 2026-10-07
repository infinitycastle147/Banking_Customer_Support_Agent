from datetime import datetime

from banking_agent.banking.masking import mask_reference
from banking_agent.config.settings import (
    MAX_TRANSACTION_RESULTS,
    TRANSACTION_READ_SCOPE,
)
from banking_agent.identity.verification import require_verified_session
from banking_agent.models.record_unavailable import RecordUnavailable
from banking_agent.models.transaction_record import TransactionRecord
from banking_agent.models.transaction_view import TransactionView
from banking_agent.models.verification_context import VerificationContext


def _view(record: TransactionRecord) -> TransactionView:
    return TransactionView(
        masked_transaction_id=mask_reference(record.transaction_id),
        masked_account=mask_reference(record.masked_account),
        merchant=record.merchant,
        amount=record.amount,
        currency=record.currency,
        status=record.status,
        occurred_at=record.occurred_at,
        bank_description=record.bank_description,
    )


class TransactionReader:
    def __init__(self, records: tuple[TransactionRecord, ...]):
        self._records = records

    def list_customer_transactions(
        self,
        context: VerificationContext | None,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> tuple[TransactionView, ...]:
        customer_id = require_verified_session(
            context, session_id=session_id, action=TRANSACTION_READ_SCOPE, now=now
        )
        owned = [
            record for record in self._records if record.customer_id == customer_id
        ]
        owned.sort(key=lambda record: record.occurred_at, reverse=True)
        return tuple(_view(record) for record in owned[:MAX_TRANSACTION_RESULTS])

    def get_transaction(
        self,
        transaction_id: str,
        context: VerificationContext | None,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> TransactionView:
        customer_id = require_verified_session(
            context, session_id=session_id, action=TRANSACTION_READ_SCOPE, now=now
        )
        for record in self._records:
            if (
                record.transaction_id == transaction_id
                and record.customer_id == customer_id
            ):
                return _view(record)
        raise RecordUnavailable("Transaction unavailable.")
