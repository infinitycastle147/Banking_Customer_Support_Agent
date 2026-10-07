from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DisputeRecord:
    dispute_id: str
    customer_id: str
    transaction_id: str
    status: str
    next_step: str
    version: int
    opened_at: datetime
    staff_notes: str
