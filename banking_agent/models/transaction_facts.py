from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class TransactionFacts:
    masked_transaction_id: str
    masked_account: str
    merchant: str
    amount: Decimal
    currency: str
    status: str
    occurred_at: datetime
