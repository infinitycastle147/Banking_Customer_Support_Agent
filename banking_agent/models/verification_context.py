from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VerificationContext:
    session_id: str
    customer_id: str
    verification_reference: str
    method: str
    permitted_actions: frozenset[str]
    verified_at: datetime
    expires_at: datetime
