from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from banking_agent.config.settings import (
    DISPUTE_READ_SCOPE,
    DISPUTE_WRITE_SCOPE,
    TRANSACTION_READ_SCOPE,
)
from banking_agent.models.dispute_record import DisputeRecord
from banking_agent.models.transaction_record import TransactionRecord
from banking_agent.models.verification_context import VerificationContext

INDIA_TIME = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 7, 14, 30, tzinfo=INDIA_TIME)


@pytest.fixture
def verified_context():
    return VerificationContext(
        session_id="demo-session-a",
        customer_id="demo-customer-a",
        verification_reference="demo-verification-a",
        method="synthetic-app-confirmation",
        permitted_actions=frozenset(
            {TRANSACTION_READ_SCOPE, DISPUTE_READ_SCOPE, DISPUTE_WRITE_SCOPE}
        ),
        verified_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=4),
    )


@pytest.fixture
def transactions():
    return (
        TransactionRecord(
            transaction_id="624810110001",
            customer_id="demo-customer-a",
            masked_account="XXXXXX1024",
            merchant="Sample Kirana Store",
            amount=Decimal("549.00"),
            currency="INR",
            status="posted",
            occurred_at=datetime(2026, 10, 6, 18, 42, tzinfo=INDIA_TIME),
            bank_description="UPI merchant payment",
        ),
        TransactionRecord(
            transaction_id="624810110002",
            customer_id="demo-customer-b",
            masked_account="XXXXXX2088",
            merchant="Sample Pharmacy",
            amount=Decimal("829.50"),
            currency="INR",
            status="posted",
            occurred_at=datetime(2026, 10, 7, 10, 15, tzinfo=INDIA_TIME),
            bank_description="IMPS transfer",
        ),
    )


@pytest.fixture
def disputes():
    return (
        DisputeRecord(
            dispute_id="DEMO-DISPUTE-001",
            customer_id="demo-customer-a",
            transaction_id="624810110001",
            status="pending_review",
            next_step="Awaiting human review",
            version=1,
            opened_at=datetime(2026, 10, 7, 11, 10, tzinfo=INDIA_TIME),
            staff_notes="Private reviewer note",
        ),
        DisputeRecord(
            dispute_id="DEMO-DISPUTE-002",
            customer_id="demo-customer-b",
            transaction_id="624810110002",
            status="pending_review",
            next_step="Awaiting human review",
            version=1,
            opened_at=datetime(2026, 10, 7, 12, 10, tzinfo=INDIA_TIME),
            staff_notes="Another private reviewer note",
        ),
    )
