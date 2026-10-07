from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DisputeCommand:
    action: Literal["create", "amend", "withdraw"]
    target_id: str
    expected_version: int
    reason_code: str
    customer_statement: str
    correlation_id: str
