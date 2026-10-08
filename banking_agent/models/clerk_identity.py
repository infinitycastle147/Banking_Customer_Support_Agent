from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClerkIdentity:
    user_id: str
    session_id: str
    expires_at: datetime
