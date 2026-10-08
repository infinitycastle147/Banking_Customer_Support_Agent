from datetime import UTC, datetime
from decimal import Decimal

from banking_agent.banking.masking import mask_reference
from banking_agent.config.settings import CASES_READ_SCOPE, DISPUTE_WRITE_SCOPE
from banking_agent.disputes.repository import DisputeStore
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.record_unavailable import RecordUnavailable
from banking_agent.models.staff_access_context import StaffAccessContext
from banking_agent.models.staff_case_report import StaffCaseReport
from banking_agent.models.system_facts import SystemFacts
from banking_agent.models.transaction_facts import TransactionFacts


def _require_staff_access(
    context: StaffAccessContext | None,
    *,
    session_id: str,
    case_id: str,
    now: datetime,
) -> None:
    if context is None or context.expires_at.tzinfo is None:
        raise AccessDenied("Staff access is required.")
    if (
        not context.staff_id
        or context.session_id != session_id
        or CASES_READ_SCOPE not in context.permitted_actions
        or case_id not in context.allowed_case_ids
        or context.expires_at <= now
    ):
        raise AccessDenied("Staff access is required.")


def build_staff_case_report(
    store: DisputeStore,
    case_id: str,
    context: StaffAccessContext | None,
    *,
    session_id: str,
    now: datetime | None = None,
) -> StaffCaseReport:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise AccessDenied("Staff access is required.")
    _require_staff_access(context, session_id=session_id, case_id=case_id, now=now)

    connection = store.connect()
    try:
        case = connection.execute(
            "SELECT c.case_id, c.dispute_id, c.requested_action, c.created_at, "
            "r.request_id, r.customer_id, r.customer_statement, r.reason_code, "
            "r.verification_reference, r.verification_method, r.verified_at, "
            "r.consent_reference, r.state AS request_state, "
            "d.transaction_id, d.status AS dispute_status, d.version AS dispute_version "
            "FROM cases c JOIN requests r ON r.request_id = c.request_id "
            "JOIN disputes d ON d.dispute_id = c.dispute_id WHERE c.case_id = ?",
            (case_id,),
        ).fetchone()
        if case is None:
            raise RecordUnavailable("Case unavailable.")
        transaction = connection.execute(
            "SELECT masked_account, merchant, amount, currency, status, occurred_at "
            "FROM synthetic_transaction_facts WHERE transaction_id = ?",
            (case["transaction_id"],),
        ).fetchone()
    finally:
        connection.close()

    facts = None
    if transaction is not None:
        facts = TransactionFacts(
            masked_transaction_id=mask_reference(case["transaction_id"]),
            masked_account=mask_reference(transaction["masked_account"]),
            merchant=transaction["merchant"],
            amount=Decimal(transaction["amount"]),
            currency=transaction["currency"],
            status=transaction["status"],
            occurred_at=datetime.fromisoformat(transaction["occurred_at"]),
        )
    action_requested = {
        "create": "Review the new dispute request and decide the next step.",
        "amend": "Review the proposed amendment and decide the next step.",
        "withdraw": "Review the withdrawal request and decide the next step.",
    }[case["requested_action"]]
    return StaffCaseReport(
        case_id=case["case_id"],
        reference_id=case["request_id"],
        dispute_id=case["dispute_id"],
        requested_action=case["requested_action"],
        verified_customer_id=case["customer_id"],
        verification_reference=case["verification_reference"],
        verification_method=case["verification_method"],
        verification_scope=DISPUTE_WRITE_SCOPE,
        verified_at=datetime.fromisoformat(case["verified_at"]),
        consent_reference=case["consent_reference"],
        customer_statement=case["customer_statement"],
        system_facts=SystemFacts(
            transaction=facts,
            dispute_status=case["dispute_status"],
            dispute_version=case["dispute_version"],
            request_state=case["request_state"],
        ),
        agent_inference=None,
        checks_performed=("verification_confirmed", "ownership_rechecked")
        + (("record_version_checked",) if case["requested_action"] != "create" else ()),
        uncertainty=None
        if facts
        else "Transaction facts are unavailable in this local pilot.",
        risk_triggers=("unauthorized_activity_claim",)
        if case["reason_code"] == "unauthorized_payment"
        else (),
        source_references=(),
        staff_action_requested=action_requested,
        created_at=datetime.fromisoformat(case["created_at"]),
    )
