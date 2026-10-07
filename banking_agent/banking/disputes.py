from datetime import datetime

from banking_agent.banking.masking import mask_reference
from banking_agent.config.settings import DISPUTE_READ_SCOPE
from banking_agent.identity.verification import require_verified_session
from banking_agent.models.dispute_record import DisputeRecord
from banking_agent.models.dispute_view import DisputeView
from banking_agent.models.record_unavailable import RecordUnavailable
from banking_agent.models.verification_context import VerificationContext


class DisputeReader:
    def __init__(self, records: tuple[DisputeRecord, ...]):
        self._records = records

    def get_dispute(
        self,
        dispute_id: str,
        context: VerificationContext | None,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> DisputeView:
        customer_id = require_verified_session(
            context, session_id=session_id, action=DISPUTE_READ_SCOPE, now=now
        )
        for record in self._records:
            if record.dispute_id == dispute_id and record.customer_id == customer_id:
                return DisputeView(
                    masked_dispute_id=mask_reference(record.dispute_id),
                    status=record.status,
                    next_step=record.next_step,
                    version=record.version,
                    opened_at=record.opened_at,
                )
        raise RecordUnavailable("Dispute unavailable.")
