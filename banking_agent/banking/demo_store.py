import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from banking_agent.config.settings import (
    TRANSACTION_READ_SCOPE,
    VERIFICATION_MAX_AGE,
    VOICE_TICKET_MAX_AGE,
)
from banking_agent.models.clerk_identity import ClerkIdentity
from banking_agent.models.transaction_record import TransactionRecord
from banking_agent.models.verification_context import VerificationContext

SAMPLE_ACTIVITY = (
    ("Greenfield Grocers", "849.50", "posted", "UPI purchase", 1),
    ("Morning Coffee", "180.00", "pending", "Card purchase", 1),
    ("Metro Transit", "65.00", "posted", "Transit payment", 2),
    ("Harbor Utilities", "2190.00", "posted", "Bill payment", 4),
    ("Northline Books", "1299.00", "reversed", "Card purchase reversal", 6),
    ("Riverside Pharmacy", "428.75", "posted", "Card purchase", 7),
    ("City Transfer", "3000.00", "failed", "IMPS transfer", 9),
    ("Salary Credit", "48500.00", "posted", "Incoming transfer", 12),
)


class DemoStore:
    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS demo_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    masked_account TEXT NOT NULL,
                    merchant TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    bank_description TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS demo_transactions_customer
                    ON demo_transactions(customer_id);
                CREATE TABLE IF NOT EXISTS demo_customers (
                    customer_id TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS voice_tickets (
                    ticket TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    clerk_session_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    identity_expires_at TEXT NOT NULL
                );
                """
            )

    def _connect(self):
        return sqlite3.connect(self._path, timeout=5)

    def ensure_customer(self, customer_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            inserted = connection.execute(
                "INSERT OR IGNORE INTO demo_customers VALUES (?)", (customer_id,)
            )
            if not inserted.rowcount:
                return
            now = datetime.now(UTC)
            masked_account = f"••••{secrets.randbelow(10000):04d}"
            for merchant, amount, status, description, days_ago in SAMPLE_ACTIVITY:
                while True:
                    reference = f"{secrets.randbelow(10**12):012d}"
                    suffix_taken = connection.execute(
                        "SELECT 1 FROM demo_transactions WHERE substr(transaction_id, -4) = ?",
                        (reference[-4:],),
                    ).fetchone()
                    if not suffix_taken:
                        break
                connection.execute(
                    "INSERT INTO demo_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        reference,
                        customer_id,
                        masked_account,
                        merchant,
                        amount,
                        "INR",
                        status,
                        (now - timedelta(days=days_ago)).isoformat(),
                        description,
                    ),
                )

    def transactions(self, customer_id: str) -> tuple[TransactionRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM demo_transactions WHERE customer_id = ?",
                (customer_id,),
            ).fetchall()
        return tuple(
            TransactionRecord(
                transaction_id=row[0],
                customer_id=row[1],
                masked_account=row[2],
                merchant=row[3],
                amount=Decimal(row[4]),
                currency=row[5],
                status=row[6],
                occurred_at=datetime.fromisoformat(row[7]),
                bank_description=row[8],
            )
            for row in rows
        )

    def create_voice_ticket(self, identity: ClerkIdentity) -> str:
        ticket = secrets.token_urlsafe(32)
        expires_at = min(identity.expires_at, datetime.now(UTC) + VOICE_TICKET_MAX_AGE)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM voice_tickets WHERE expires_at <= ?",
                (datetime.now(UTC).isoformat(),),
            )
            connection.execute(
                "INSERT INTO voice_tickets VALUES (?, ?, ?, ?, ?)",
                (
                    ticket,
                    identity.user_id,
                    identity.session_id,
                    expires_at.isoformat(),
                    identity.expires_at.isoformat(),
                ),
            )
        return ticket

    def redeem_voice_ticket(self, ticket: str) -> VerificationContext | None:
        if not ticket or len(ticket) > 128:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "DELETE FROM voice_tickets WHERE ticket = ? RETURNING customer_id, "
                "clerk_session_id, expires_at, identity_expires_at",
                (ticket,),
            ).fetchone()
        now = datetime.now(UTC)
        if row is None or datetime.fromisoformat(row[2]) <= now:
            return None
        self.ensure_customer(row[0])
        return VerificationContext(
            session_id=ticket,
            customer_id=row[0],
            verification_reference=row[1],
            method="clerk-session",
            permitted_actions=frozenset({TRANSACTION_READ_SCOPE}),
            verified_at=now,
            expires_at=min(datetime.fromisoformat(row[3]), now + VERIFICATION_MAX_AGE),
        )
