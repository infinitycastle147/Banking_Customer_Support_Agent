from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConsentGrant:
    session_id: str
    customer_id: str
    command_digest: str
    consent_reference: str
    idempotency_key: str
    confirmed_at: datetime
