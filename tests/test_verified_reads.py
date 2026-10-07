from dataclasses import replace
from datetime import timedelta

import pytest
from conftest import NOW

from banking_agent.banking.disputes import DisputeReader
from banking_agent.banking.masking import mask_reference
from banking_agent.banking.transactions import TransactionReader
from banking_agent.config.settings import TRANSACTION_READ_SCOPE
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.record_unavailable import RecordUnavailable


def test_owned_transaction_read_is_masked_and_in_inr(verified_context, transactions):
    reader = TransactionReader(transactions)

    result = reader.get_transaction(
        "624810110001", verified_context, session_id="demo-session-a", now=NOW
    )

    assert result.masked_transaction_id == "••••0001"
    assert result.masked_account == "••••1024"
    assert result.currency == "INR"
    assert result.occurred_at.utcoffset() == timedelta(hours=5, minutes=30)
    assert not hasattr(result, "customer_id")


def test_list_only_returns_verified_customer_records(verified_context, transactions):
    result = TransactionReader(transactions).list_customer_transactions(
        verified_context, session_id="demo-session-a", now=NOW
    )

    assert len(result) == 1
    assert result[0].merchant == "Sample Kirana Store"


@pytest.mark.parametrize("transaction_id", ["624810110002", "unknown"])
def test_cross_customer_and_unknown_transaction_have_same_denial(
    verified_context, transactions, transaction_id
):
    with pytest.raises(RecordUnavailable) as error:
        TransactionReader(transactions).get_transaction(
            transaction_id, verified_context, session_id="demo-session-a", now=NOW
        )
    assert str(error.value) == "Transaction unavailable."


@pytest.mark.parametrize(
    "context_change,session_id,now",
    [
        ({}, "other-session", NOW),
        ({"permitted_actions": frozenset()}, "demo-session-a", NOW),
        ({}, "demo-session-a", NOW + timedelta(minutes=4)),
        ({"expires_at": NOW + timedelta(days=1)}, "demo-session-a", NOW),
    ],
)
def test_invalid_verification_cannot_read(
    verified_context, transactions, context_change, session_id, now
):
    context = replace(verified_context, **context_change)
    with pytest.raises(AccessDenied, match="Verification is required"):
        TransactionReader(transactions).get_transaction(
            "624810110001", context, session_id=session_id, now=now
        )


def test_missing_verification_cannot_list(transactions):
    with pytest.raises(AccessDenied, match="Verification is required"):
        TransactionReader(transactions).list_customer_transactions(
            None, session_id="demo-session-a", now=NOW
        )


def test_dispute_view_omits_staff_notes(verified_context, disputes):
    result = DisputeReader(disputes).get_dispute(
        "DEMO-DISPUTE-001", verified_context, session_id="demo-session-a", now=NOW
    )

    assert result.status == "pending_review"
    assert result.next_step == "Awaiting human review"
    assert result.masked_dispute_id == "••••-001"
    assert not hasattr(result, "staff_notes")
    assert not hasattr(result, "customer_id")


@pytest.mark.parametrize("dispute_id", ["DEMO-DISPUTE-002", "unknown"])
def test_cross_customer_and_unknown_dispute_have_same_denial(
    verified_context, disputes, dispute_id
):
    with pytest.raises(RecordUnavailable) as error:
        DisputeReader(disputes).get_dispute(
            dispute_id, verified_context, session_id="demo-session-a", now=NOW
        )
    assert str(error.value) == "Dispute unavailable."


def test_scope_is_checked_for_each_read(verified_context, disputes):
    context = replace(
        verified_context, permitted_actions=frozenset({TRANSACTION_READ_SCOPE})
    )
    with pytest.raises(AccessDenied, match="Verification is required"):
        DisputeReader(disputes).get_dispute(
            "DEMO-DISPUTE-001", context, session_id="demo-session-a", now=NOW
        )


def test_short_reference_is_fully_masked():
    assert mask_reference("abc") == "••••"
