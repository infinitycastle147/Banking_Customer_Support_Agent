from dataclasses import dataclass
from datetime import datetime

from banking_agent.models.source_reference import SourceReference
from banking_agent.models.system_facts import SystemFacts


@dataclass(frozen=True)
class StaffCaseReport:
    case_id: str
    reference_id: str
    dispute_id: str
    requested_action: str
    verified_customer_id: str
    verification_reference: str
    verification_method: str
    verification_scope: str
    verified_at: datetime
    consent_reference: str
    customer_statement: str
    system_facts: SystemFacts
    agent_inference: str | None
    checks_performed: tuple[str, ...]
    uncertainty: str | None
    risk_triggers: tuple[str, ...]
    source_references: tuple[SourceReference, ...]
    staff_action_requested: str
    created_at: datetime
