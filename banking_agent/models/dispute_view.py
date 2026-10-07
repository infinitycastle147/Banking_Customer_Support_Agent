from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DisputeView:
    masked_dispute_id: str
    status: str
    next_step: str
    version: int
    opened_at: datetime
