import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from banking_agent.config.settings import DISPUTE_WRITE_SCOPE
from banking_agent.identity.verification import require_verified_session
from banking_agent.models.consent_grant import ConsentGrant
from banking_agent.models.dispute_command import DisputeCommand
from banking_agent.models.verification_context import VerificationContext


def command_digest(command: DisputeCommand) -> str:
    payload = {
        "action": command.action,
        "target_id": command.target_id,
        "expected_version": command.expected_version,
        "reason_code": command.reason_code,
        "customer_statement": command.customer_statement,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def issue_consent_grant(
    command: DisputeCommand,
    context: VerificationContext,
    *,
    session_id: str,
    readback_acknowledged: bool,
    now: datetime | None = None,
) -> ConsentGrant:
    if not readback_acknowledged:
        raise ValueError("Explicit readback consent is required.")
    now = now or datetime.now(UTC)
    customer_id = require_verified_session(
        context, session_id=session_id, action=DISPUTE_WRITE_SCOPE, now=now
    )
    return ConsentGrant(
        session_id=session_id,
        customer_id=customer_id,
        command_digest=command_digest(command),
        consent_reference=str(uuid4()),
        idempotency_key=str(uuid4()),
        confirmed_at=now,
    )
