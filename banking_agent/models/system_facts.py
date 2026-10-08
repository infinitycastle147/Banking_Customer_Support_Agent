from dataclasses import dataclass

from banking_agent.models.transaction_facts import TransactionFacts


@dataclass(frozen=True)
class SystemFacts:
    transaction: TransactionFacts | None
    dispute_status: str
    dispute_version: int
    request_state: str
