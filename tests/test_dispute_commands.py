from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest
from conftest import NOW

from banking_agent.disputes.command_service import DisputeCommandService
from banking_agent.disputes.consent import issue_consent_grant
from banking_agent.disputes.repository import DisputeStore
from banking_agent.disputes.worker import DisputeWorker
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.dispute_command import DisputeCommand


@pytest.fixture
def store(tmp_path):
    store = DisputeStore(tmp_path / "disputes.sqlite")
    store.initialize()
    seed_transaction(store, "624810110001", "demo-customer-a")
    seed_transaction(store, "624810110002", "demo-customer-b")
    return store


@pytest.fixture
def create_command():
    return DisputeCommand(
        action="create",
        target_id="624810110001",
        expected_version=0,
        reason_code="unauthorized_payment",
        customer_statement="I do not recognize this sample UPI payment.",
        correlation_id="demo-correlation-1",
    )


def consent_for(command, context):
    return issue_consent_grant(
        command,
        context,
        session_id="demo-session-a",
        readback_acknowledged=True,
        now=NOW,
    )


def seed_transaction(store, transaction_id, customer_id):
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO synthetic_transactions (transaction_id, customer_id) VALUES (?, ?)",
            (transaction_id, customer_id),
        )
        connection.execute(
            "INSERT INTO synthetic_transaction_facts "
            "(transaction_id, masked_account, merchant, amount, currency, status, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                transaction_id,
                "XXXXXX1024",
                "Sample Kirana Store",
                "549.00",
                "INR",
                "posted",
                NOW.isoformat(),
            ),
        )


def submit(store, command, context, consent=None):
    return DisputeCommandService(store).submit(
        command,
        consent if consent is not None else consent_for(command, context),
        context,
        session_id="demo-session-a",
        now=NOW,
    )


def counts(store):
    connection = store.connect()
    try:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("requests", "outbox", "disputes", "dispute_history", "cases")
        )
    finally:
        connection.close()


def test_confirmation_and_verification_are_required(
    store, create_command, verified_context
):
    service = DisputeCommandService(store)
    assert (
        service.submit(
            create_command, None, verified_context, session_id="demo-session-a", now=NOW
        ).code
        == "validation_failed"
    )
    assert (
        service.submit(
            create_command, None, None, session_id="demo-session-a", now=NOW
        ).code
        == "unauthorized"
    )
    with pytest.raises(ValueError, match="Explicit readback consent"):
        issue_consent_grant(
            create_command,
            verified_context,
            session_id="demo-session-a",
            readback_acknowledged=False,
            now=NOW,
        )
    with pytest.raises(AccessDenied):
        issue_consent_grant(
            create_command,
            verified_context,
            session_id="other-session",
            readback_acknowledged=True,
            now=NOW,
        )
    assert counts(store) == (0, 0, 0, 0, 0)


def test_consent_is_bound_to_action_fields_and_expires(
    store, create_command, verified_context
):
    consent = consent_for(create_command, verified_context)
    changed = replace(create_command, customer_statement="Different request")
    assert submit(store, changed, verified_context, consent).code == "validation_failed"
    assert (
        DisputeCommandService(store)
        .submit(
            create_command,
            consent,
            verified_context,
            session_id="demo-session-a",
            now=NOW + timedelta(minutes=3),
        )
        .code
        == "validation_failed"
    )
    assert counts(store) == (0, 0, 0, 0, 0)


def test_atomic_acceptance_worker_and_status(store, create_command, verified_context):
    consent = consent_for(create_command, verified_context)
    outcome = submit(store, create_command, verified_context, consent)

    assert outcome.code == "accepted"
    assert outcome.request_id
    assert outcome.request_state == "accepted"
    assert counts(store) == (1, 1, 0, 0, 0)

    status = DisputeCommandService(store).get_request_status(
        verified_context,
        session_id="demo-session-a",
        idempotency_key=consent.idempotency_key,
        now=NOW,
    )
    assert status.request_id == outcome.request_id
    assert status.request_state == "accepted"

    assert DisputeWorker(store).process_one(now=NOW) == outcome.request_id
    assert counts(store) == (1, 1, 1, 1, 1)
    connection = store.connect()
    try:
        dispute = connection.execute("SELECT status, version FROM disputes").fetchone()
        assert (dispute["status"], dispute["version"]) == ("pending_review", 1)
    finally:
        connection.close()
    status = DisputeCommandService(store).get_request_status(
        verified_context,
        session_id="demo-session-a",
        request_id=outcome.request_id,
        now=NOW,
    )
    assert status.code == "accepted"
    assert status.request_state == "processed"
    assert "human review" in status.message


def test_retry_and_replay_do_not_duplicate_effects(
    store, create_command, verified_context
):
    consent = consent_for(create_command, verified_context)
    first = submit(store, create_command, verified_context, consent)
    repeated = submit(store, create_command, verified_context, consent)
    assert repeated.code == "already_submitted"
    assert repeated.request_id == first.request_id
    assert DisputeWorker(store).process_one(now=NOW) == first.request_id

    with store.transaction() as connection:
        connection.execute("UPDATE outbox SET state = 'pending'")
    assert DisputeWorker(store).process_one(now=NOW) == first.request_id
    assert counts(store) == (1, 1, 1, 1, 1)


def test_idempotency_key_cannot_be_reused_for_another_action(
    store, create_command, verified_context
):
    first_consent = consent_for(create_command, verified_context)
    assert (
        submit(store, create_command, verified_context, first_consent).code
        == "accepted"
    )
    changed = replace(create_command, customer_statement="A different sample claim")
    changed_consent = replace(
        consent_for(changed, verified_context),
        idempotency_key=first_consent.idempotency_key,
    )

    outcome = submit(store, changed, verified_context, changed_consent)

    assert outcome.code == "validation_failed"
    assert counts(store) == (1, 1, 0, 0, 0)


def test_parallel_duplicate_submission_has_one_request(
    store, create_command, verified_context
):
    consent = consent_for(create_command, verified_context)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: submit(store, create_command, verified_context, consent),
                range(2),
            )
        )

    assert {result.code for result in results} == {"accepted", "already_submitted"}
    assert len({result.request_id for result in results}) == 1
    assert counts(store) == (1, 1, 0, 0, 0)


def test_parallel_business_duplicates_have_one_request(
    store, create_command, verified_context
):
    grants = [consent_for(create_command, verified_context) for _ in range(2)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda grant: submit(store, create_command, verified_context, grant),
                grants,
            )
        )

    assert {result.code for result in results} == {"accepted", "already_submitted"}
    assert len({result.request_id for result in results}) == 1
    assert counts(store) == (1, 1, 0, 0, 0)


def test_business_duplicate_and_cross_customer_denial(
    store, create_command, verified_context
):
    first = submit(store, create_command, verified_context)
    other_consent = consent_for(create_command, verified_context)
    second = submit(store, create_command, verified_context, other_consent)
    assert second.code == "already_submitted"
    assert second.request_id == first.request_id

    foreign_command = replace(create_command, target_id="624810110002")
    assert submit(store, foreign_command, verified_context).code == "unauthorized"
    assert counts(store) == (1, 1, 0, 0, 0)


def test_outbox_insert_failure_rolls_back_request(
    store, create_command, verified_context
):
    with store.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER reject_outbox BEFORE INSERT ON outbox "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )

    outcome = submit(store, create_command, verified_context)
    assert outcome.code == "temporarily_unavailable"
    assert outcome.retryable
    assert counts(store) == (0, 0, 0, 0, 0)


def test_repeated_worker_failure_goes_to_dead_letter(
    store, create_command, verified_context
):
    accepted = submit(store, create_command, verified_context)
    with store.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER reject_dispute BEFORE INSERT ON disputes "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )

    worker = DisputeWorker(store)
    for _ in range(3):
        assert worker.process_one(now=NOW) is None

    connection = store.connect()
    try:
        event = connection.execute("SELECT state, attempts FROM outbox").fetchone()
        request = connection.execute("SELECT state FROM requests").fetchone()
        assert (event["state"], event["attempts"]) == ("dead_letter", 3)
        assert request["state"] == "accepted"
    finally:
        connection.close()
    assert counts(store) == (1, 1, 0, 0, 0)

    with store.transaction() as connection:
        connection.execute("DROP TRIGGER reject_dispute")
        connection.execute("UPDATE outbox SET state = 'pending'")
    assert worker.process_one(now=NOW) == accepted.request_id
    assert counts(store) == (1, 1, 1, 1, 1)


def test_session_rate_limit_is_enforced(store, create_command, verified_context):
    for index in range(3, 7):
        seed_transaction(store, f"6248101100{index:02}", "demo-customer-a")

    outcomes = [submit(store, create_command, verified_context)]
    for index in range(3, 6):
        command = replace(create_command, target_id=f"6248101100{index:02}")
        outcomes.append(submit(store, command, verified_context))

    assert [outcome.code for outcome in outcomes] == [
        "accepted",
        "accepted",
        "accepted",
        "rate_limited",
    ]
    assert counts(store) == (3, 3, 0, 0, 0)


def test_request_status_does_not_reveal_other_customer_request(
    store, create_command, verified_context
):
    accepted = submit(store, create_command, verified_context)
    other_customer = replace(verified_context, customer_id="demo-customer-b")
    status = DisputeCommandService(store).get_request_status(
        other_customer,
        session_id="demo-session-a",
        request_id=accepted.request_id,
        now=NOW,
    )
    unknown = DisputeCommandService(store).get_request_status(
        other_customer,
        session_id="demo-session-a",
        request_id="unknown",
        now=NOW,
    )
    assert status == unknown


def test_stale_amendment_is_rejected_by_worker(store, create_command, verified_context):
    submit(store, create_command, verified_context)
    DisputeWorker(store).process_one(now=NOW)
    connection = store.connect()
    try:
        dispute_id = connection.execute("SELECT dispute_id FROM disputes").fetchone()[0]
    finally:
        connection.close()

    amend = DisputeCommand(
        action="amend",
        target_id=dispute_id,
        expected_version=1,
        reason_code="unauthorized_payment",
        customer_statement="Please add that I checked my sample UPI history.",
        correlation_id="demo-correlation-2",
    )
    accepted = submit(store, amend, verified_context)
    assert accepted.code == "accepted"
    with store.transaction() as connection:
        connection.execute(
            "UPDATE disputes SET version = 2 WHERE dispute_id = ?", (dispute_id,)
        )

    DisputeWorker(store).process_one(now=NOW)
    status = DisputeCommandService(store).get_request_status(
        verified_context,
        session_id="demo-session-a",
        request_id=accepted.request_id,
        now=NOW,
    )
    assert status.code == "stale_version"
    assert status.request_state == "rejected"
    assert counts(store) == (2, 2, 1, 1, 1)


def test_withdrawal_keeps_history_and_needs_human_review(
    store, create_command, verified_context
):
    submit(store, create_command, verified_context)
    DisputeWorker(store).process_one(now=NOW)
    connection = store.connect()
    try:
        dispute_id = connection.execute("SELECT dispute_id FROM disputes").fetchone()[0]
    finally:
        connection.close()

    withdrawal = DisputeCommand(
        action="withdraw",
        target_id=dispute_id,
        expected_version=1,
        reason_code="",
        customer_statement="I want to withdraw this sample claim.",
        correlation_id="demo-correlation-3",
    )
    assert submit(store, withdrawal, verified_context).code == "accepted"
    DisputeWorker(store).process_one(now=NOW)
    connection = store.connect()
    try:
        dispute = connection.execute("SELECT status, version FROM disputes").fetchone()
        assert (dispute["status"], dispute["version"]) == (
            "withdrawal_pending_review",
            2,
        )
    finally:
        connection.close()
    assert counts(store) == (2, 2, 1, 2, 2)
