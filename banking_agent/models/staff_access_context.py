from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StaffAccessContext:
    staff_id: str
    session_id: str
    permitted_actions: frozenset[str]
    allowed_case_ids: frozenset[str]
    expires_at: datetime
