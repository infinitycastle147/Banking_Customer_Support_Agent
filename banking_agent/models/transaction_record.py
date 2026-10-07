from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: str
    customer_id: str
    masked_account: str
    merchant: str
    amount: Decimal
    currency: str
    status: str
    occurred_at: datetime
    bank_description: str
