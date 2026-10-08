from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from conftest import NOW

from banking_agent.cases.notifications import build_staff_notification
from banking_agent.cases.report import build_staff_case_report
from banking_agent.config.settings import CASES_READ_SCOPE
from banking_agent.disputes.command_service import DisputeCommandService
from banking_agent.disputes.consent import issue_consent_grant
from banking_agent.disputes.repository import DisputeStore
from banking_agent.disputes.worker import DisputeWorker
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.dispute_command import DisputeCommand
from banking_agent.models.record_unavailable import RecordUnavailable
from banking_agent.models.staff_access_context import StaffAccessContext


@pytest.fixture
def case_fixture(tmp_path, verified_context):
    store = DisputeStore(tmp_path / "cases.sqlite")
    store.initialize()
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO synthetic_transactions (transaction_id, customer_id) VALUES (?, ?)",
            ("624810110001", "demo-customer-a"),
        )
        connection.execute(
            "INSERT INTO synthetic_transaction_facts "
            "(transaction_id, masked_account, merchant, amount, currency, status, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "624810110001",
                "XXXXXX1024",
                "Sample Kirana Store",
                "549.00",
                "INR",
                "posted",
                NOW.isoformat(),
            ),
        )
    command = DisputeCommand(
        action="create",
        target_id="624810110001",
        expected_version=0,
        reason_code="unauthorized_payment",
        customer_statement="I did not authorize this sample payment.",
        correlation_id="demo-case-correlation",
    )
    consent = issue_consent_grant(
        command,
        verified_context,
        session_id="demo-session-a",
        readback_acknowledged=True,
        now=NOW,
    )
    outcome = DisputeCommandService(store).submit(
        command, consent, verified_context, session_id="demo-session-a", now=NOW
    )
    assert outcome.code == "accepted"
    DisputeWorker(store).process_one(now=NOW)
    connection = store.connect()
    try:
        case_id = connection.execute("SELECT case_id FROM cases").fetchone()[0]
    finally:
        connection.close()
    staff_context = StaffAccessContext(
        staff_id="demo-reviewer-a",
        session_id="demo-staff-session",
        permitted_actions=frozenset({CASES_READ_SCOPE}),
        allowed_case_ids=frozenset({case_id}),
        expires_at=NOW + timedelta(minutes=10),
    )
    return store, case_id, staff_context, consent


def test_staff_case_separates_statement_facts_and_inference(case_fixture):
    store, case_id, context, consent = case_fixture

    report = build_staff_case_report(
        store, case_id, context, session_id="demo-staff-session", now=NOW
    )

    assert report.customer_statement == "I did not authorize this sample payment."
    assert report.agent_inference is None
    assert report.verified_customer_id == "demo-customer-a"
    assert report.verification_method == "synthetic-app-confirmation"
    assert report.verification_scope == "disputes:write"
    assert report.consent_reference == consent.consent_reference
    assert report.system_facts.dispute_status == "pending_review"
    assert report.system_facts.request_state == "processed"
    assert report.system_facts.transaction.masked_transaction_id == "••••0001"
    assert report.system_facts.transaction.masked_account == "••••1024"
    assert report.system_facts.transaction.currency == "INR"
    assert report.risk_triggers == ("unauthorized_activity_claim",)
    assert report.source_references == ()
    assert report.checks_performed == ("verification_confirmed", "ownership_rechecked")


def test_staff_notification_contains_only_reference_and_redacted_summary(case_fixture):
    store, case_id, context, _ = case_fixture
    report = build_staff_case_report(
        store, case_id, context, session_id="demo-staff-session", now=NOW
    )

    notification = build_staff_notification(
        report, secure_case_base_url="https://cases.example.test"
    )
    payload = str(asdict(notification))

    assert notification.priority == "urgent"
    assert notification.reference_id == report.reference_id
    assert notification.secure_case_link.endswith(f"/cases/{case_id}")
    for sensitive in (
        "demo-customer-a",
        "I did not authorize",
        "Sample Kirana Store",
        "549.00",
        "1024",
    ):
        assert sensitive not in payload


@pytest.mark.parametrize(
    "context_change,session_id",
    [
        ({"allowed_case_ids": frozenset()}, "demo-staff-session"),
        ({"permitted_actions": frozenset()}, "demo-staff-session"),
        ({"expires_at": NOW - timedelta(seconds=1)}, "demo-staff-session"),
        ({}, "other-session"),
    ],
)
def test_staff_case_requires_scoped_staff_session(
    case_fixture, context_change, session_id
):
    store, case_id, context, _ = case_fixture

    with pytest.raises(AccessDenied, match="Staff access is required"):
        build_staff_case_report(
            store,
            case_id,
            replace(context, **context_change),
            session_id=session_id,
            now=NOW,
        )


def test_unknown_assigned_case_is_unavailable(case_fixture):
    store, _, context, _ = case_fixture
    context = replace(context, allowed_case_ids=frozenset({"unknown-case"}))

    with pytest.raises(RecordUnavailable, match="Case unavailable"):
        build_staff_case_report(
            store, "unknown-case", context, session_id="demo-staff-session", now=NOW
        )


def test_missing_transaction_facts_are_reported_as_uncertainty(case_fixture):
    store, case_id, context, _ = case_fixture
    with store.transaction() as connection:
        connection.execute("DELETE FROM synthetic_transaction_facts")

    report = build_staff_case_report(
        store, case_id, context, session_id="demo-staff-session", now=NOW
    )

    assert report.system_facts.transaction is None
    assert (
        report.uncertainty == "Transaction facts are unavailable in this local pilot."
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://cases.example.test",
        "https://user:pass@cases.example.test",
        "https://cases.example.test?key=x",
    ],
)
def test_notification_requires_secure_base_url(case_fixture, base_url):
    store, case_id, context, _ = case_fixture
    report = build_staff_case_report(
        store, case_id, context, session_id="demo-staff-session", now=NOW
    )

    with pytest.raises(ValueError, match="secure HTTPS"):
        build_staff_notification(report, secure_case_base_url=base_url)
