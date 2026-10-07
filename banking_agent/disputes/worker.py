import logging
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from banking_agent.config.settings import (
    OUTBOX_POLL_INTERVAL_SECONDS,
    PILOT_MUTABLE_DISPUTE_STATES,
    PILOT_OUTBOX_MAX_ATTEMPTS,
)
from banking_agent.disputes.repository import DisputeStore

logger = logging.getLogger(__name__)


def _apply_request(connection, request, now: datetime) -> str:
    if request["action"] not in {"create", "amend", "withdraw"}:
        return "validation_failed"
    if not request["verification_reference"] or not request["consent_reference"]:
        return "unauthorized"
    if request["action"] == "create":
        transaction = connection.execute(
            "SELECT customer_id FROM synthetic_transactions WHERE transaction_id = ?",
            (request["target_id"],),
        ).fetchone()
        if transaction is None or transaction["customer_id"] != request["customer_id"]:
            return "unauthorized"
        duplicate = connection.execute(
            "SELECT 1 FROM disputes WHERE customer_id = ? AND transaction_id = ? "
            "AND reason_code = ? AND status != 'withdrawn' LIMIT 1",
            (request["customer_id"], request["target_id"], request["reason_code"]),
        ).fetchone()
        if duplicate:
            return "existing_dispute"
        dispute_id = str(uuid4())
        connection.execute(
            "INSERT INTO disputes "
            "(dispute_id, customer_id, transaction_id, reason_code, status, version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                dispute_id,
                request["customer_id"],
                request["target_id"],
                request["reason_code"],
                "pending_review",
                1,
                now.isoformat(),
            ),
        )
    else:
        dispute = connection.execute(
            "SELECT customer_id, version, status FROM disputes WHERE dispute_id = ?",
            (request["target_id"],),
        ).fetchone()
        if dispute is None or dispute["customer_id"] != request["customer_id"]:
            return "unauthorized"
        if dispute["version"] != request["expected_version"]:
            return "stale_version"
        if dispute["status"] not in PILOT_MUTABLE_DISPUTE_STATES:
            return "invalid_state"
        dispute_id = request["target_id"]
        status = (
            "change_pending_review"
            if request["action"] == "amend"
            else "withdrawal_pending_review"
        )
        updated = connection.execute(
            "UPDATE disputes SET status = ?, version = version + 1 "
            "WHERE dispute_id = ? AND version = ?",
            (status, dispute_id, request["expected_version"]),
        )
        if updated.rowcount != 1:
            return "stale_version"

    connection.execute(
        "INSERT INTO dispute_history "
        "(dispute_id, request_id, action, customer_statement, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            dispute_id,
            request["request_id"],
            request["action"],
            request["customer_statement"],
            now.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO cases "
        "(case_id, request_id, customer_id, dispute_id, requested_action, state, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid4()),
            request["request_id"],
            request["customer_id"],
            dispute_id,
            request["action"],
            "pending_staff_review",
            now.isoformat(),
        ),
    )
    return "processed"


class DisputeWorker:
    def __init__(self, store: DisputeStore):
        self._store = store

    def process_one(self, *, now: datetime | None = None) -> str | None:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        event_id = None
        try:
            with self._store.transaction() as connection:
                event = connection.execute(
                    "SELECT event_id, request_id FROM outbox WHERE state = 'pending' "
                    "ORDER BY rowid LIMIT 1"
                ).fetchone()
                if event is None:
                    return None
                event_id = event["event_id"]
                request = connection.execute(
                    "SELECT * FROM requests WHERE request_id = ?",
                    (event["request_id"],),
                ).fetchone()
                if request["state"] == "accepted":
                    result = _apply_request(connection, request, now)
                    connection.execute(
                        "UPDATE requests SET state = ?, result_code = ? WHERE request_id = ?",
                        (
                            "processed" if result == "processed" else "rejected",
                            result,
                            request["request_id"],
                        ),
                    )
                connection.execute(
                    "UPDATE outbox SET state = 'delivered' WHERE event_id = ?",
                    (event_id,),
                )
                return event["request_id"]
        except sqlite3.Error:
            if event_id is not None:
                self._record_failure(event_id)
            logger.exception("disputes.worker_failed")
            return None

    def _record_failure(self, event_id: str) -> None:
        try:
            with self._store.transaction() as connection:
                connection.execute(
                    "UPDATE outbox SET attempts = attempts + 1, "
                    "state = CASE WHEN attempts + 1 >= ? THEN 'dead_letter' ELSE 'pending' END "
                    "WHERE event_id = ? AND state = 'pending'",
                    (PILOT_OUTBOX_MAX_ATTEMPTS, event_id),
                )
        except sqlite3.Error:
            logger.exception("disputes.failure_record_failed")


def main() -> None:
    database_path = os.getenv("DISPUTE_DB_PATH", "").strip()
    if not database_path:
        raise ValueError("DISPUTE_DB_PATH is required")
    worker = DisputeWorker(DisputeStore(Path(database_path)))
    while True:
        if worker.process_one() is None:
            time.sleep(OUTBOX_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
