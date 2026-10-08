import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from banking_agent.audit.events import record_audit_event
from banking_agent.config.settings import (
    CONSENT_MAX_AGE,
    DISPUTE_READ_SCOPE,
    DISPUTE_WRITE_SCOPE,
    PILOT_CUSTOMER_REQUEST_LIMIT_PER_HOUR,
    PILOT_MUTABLE_DISPUTE_STATES,
    PILOT_SESSION_REQUEST_LIMIT_PER_HOUR,
    PILOT_TARGET_REQUEST_LIMIT_PER_HOUR,
)
from banking_agent.disputes.consent import command_digest
from banking_agent.disputes.repository import DisputeStore
from banking_agent.identity.verification import require_verified_session
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.command_outcome import CommandOutcome
from banking_agent.models.consent_grant import ConsentGrant
from banking_agent.models.dispute_command import DisputeCommand
from banking_agent.models.verification_context import VerificationContext


def _outcome(
    code: str,
    correlation_id: str,
    message: str,
    *,
    request_id: str | None = None,
    request_state: str | None = None,
    retryable: bool = False,
) -> CommandOutcome:
    return CommandOutcome(
        code=code,
        message=message,
        correlation_id=correlation_id,
        request_id=request_id,
        request_state=request_state,
        retryable=retryable,
    )


def _valid_command(command: DisputeCommand) -> bool:
    if command.action not in {"create", "amend", "withdraw"}:
        return False
    if not isinstance(command.target_id, str) or not 1 <= len(command.target_id) <= 100:
        return False
    if type(command.expected_version) is not int or command.expected_version < 0:
        return False
    if (
        not isinstance(command.correlation_id, str)
        or not 1 <= len(command.correlation_id) <= 100
    ):
        return False
    if not isinstance(command.reason_code, str) or len(command.reason_code) > 50:
        return False
    if (
        not isinstance(command.customer_statement, str)
        or len(command.customer_statement) > 2000
    ):
        return False
    if command.action == "create":
        return (
            command.expected_version == 0
            and bool(command.reason_code.strip())
            and bool(command.customer_statement.strip())
        )
    if command.action == "amend":
        return command.expected_version > 0 and bool(command.customer_statement.strip())
    return command.expected_version > 0


def _consent_matches(
    command: DisputeCommand,
    consent: ConsentGrant | None,
    *,
    customer_id: str,
    session_id: str,
    now: datetime,
) -> bool:
    if consent is None:
        return False
    if consent.confirmed_at.tzinfo is None or consent.confirmed_at.utcoffset() is None:
        return False
    return (
        consent.customer_id == customer_id
        and consent.session_id == session_id
        and consent.command_digest == command_digest(command)
        and bool(consent.consent_reference)
        and bool(consent.idempotency_key)
        and consent.confirmed_at <= now
    )


def _rate_limited(
    connection, customer_id: str, session_id: str, target_id: str, now: datetime
) -> bool:
    since = (now - timedelta(hours=1)).isoformat()
    customer_count = connection.execute(
        "SELECT COUNT(*) FROM requests WHERE customer_id = ? AND created_at >= ?",
        (customer_id, since),
    ).fetchone()[0]
    session_count = connection.execute(
        "SELECT COUNT(*) FROM requests WHERE customer_id = ? AND session_id = ? AND created_at >= ?",
        (customer_id, session_id, since),
    ).fetchone()[0]
    target_count = connection.execute(
        "SELECT COUNT(*) FROM requests WHERE customer_id = ? AND target_id = ? AND created_at >= ?",
        (customer_id, target_id, since),
    ).fetchone()[0]
    return (
        customer_count >= PILOT_CUSTOMER_REQUEST_LIMIT_PER_HOUR
        or session_count >= PILOT_SESSION_REQUEST_LIMIT_PER_HOUR
        or target_count >= PILOT_TARGET_REQUEST_LIMIT_PER_HOUR
    )


def _validate_target(
    connection, customer_id: str, command: DisputeCommand
) -> str | None:
    if command.action == "create":
        transaction = connection.execute(
            "SELECT customer_id FROM synthetic_transactions WHERE transaction_id = ?",
            (command.target_id,),
        ).fetchone()
        if transaction is None or transaction["customer_id"] != customer_id:
            return "unauthorized"
        existing = connection.execute(
            "SELECT dispute_id FROM disputes WHERE customer_id = ? AND transaction_id = ? "
            "AND reason_code = ? AND status != 'withdrawn' LIMIT 1",
            (customer_id, command.target_id, command.reason_code),
        ).fetchone()
        if existing:
            return "existing_dispute"
        return None

    dispute = connection.execute(
        "SELECT customer_id, version, status FROM disputes WHERE dispute_id = ?",
        (command.target_id,),
    ).fetchone()
    if dispute is None or dispute["customer_id"] != customer_id:
        return "unauthorized"
    if dispute["version"] != command.expected_version:
        return "stale_version"
    if dispute["status"] not in PILOT_MUTABLE_DISPUTE_STATES:
        return "invalid_state"
    return None


def _existing_request(connection, customer_id: str, command: DisputeCommand):
    return connection.execute(
        "SELECT request_id, state, customer_statement, reason_code FROM requests "
        "WHERE customer_id = ? AND action = ? AND target_id = ? "
        "AND state IN ('accepted', 'processed') ORDER BY created_at DESC LIMIT 1",
        (customer_id, command.action, command.target_id),
    ).fetchone()


class DisputeCommandService:
    def __init__(self, store: DisputeStore):
        self._store = store

    def submit(
        self,
        command: DisputeCommand,
        consent: ConsentGrant | None,
        context: VerificationContext | None,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> CommandOutcome:
        now = now or datetime.now(UTC)
        correlation_id = command.correlation_id
        try:
            customer_id = require_verified_session(
                context, session_id=session_id, action=DISPUTE_WRITE_SCOPE, now=now
            )
        except AccessDenied:
            return _outcome("unauthorized", correlation_id, "Verification is required.")
        if not _valid_command(command) or not _consent_matches(
            command, consent, customer_id=customer_id, session_id=session_id, now=now
        ):
            return _outcome(
                "validation_failed", correlation_id, "Confirm the request again."
            )

        now = now.astimezone(UTC)
        try:
            with self._store.transaction() as connection:
                prior = connection.execute(
                    "SELECT request_id, state, command_digest FROM requests "
                    "WHERE customer_id = ? AND idempotency_key = ?",
                    (customer_id, consent.idempotency_key),
                ).fetchone()
                if prior:
                    if prior["command_digest"] != consent.command_digest:
                        return _outcome(
                            "validation_failed",
                            correlation_id,
                            "Confirm the request again.",
                        )
                    return _outcome(
                        "already_submitted",
                        correlation_id,
                        "This request was already submitted for review.",
                        request_id=prior["request_id"],
                        request_state=prior["state"],
                    )
                if now - consent.confirmed_at.astimezone(UTC) > CONSENT_MAX_AGE:
                    return _outcome(
                        "validation_failed",
                        correlation_id,
                        "Confirm the request again.",
                    )

                target_error = _validate_target(connection, customer_id, command)
                if target_error:
                    return _outcome(
                        target_error,
                        correlation_id,
                        {
                            "unauthorized": "The selected record is unavailable.",
                            "existing_dispute": "An eligible dispute already exists for this transaction.",
                            "stale_version": "The dispute changed. Please review it again.",
                            "invalid_state": "This dispute cannot be changed in its current state.",
                        }[target_error],
                    )

                duplicate = _existing_request(connection, customer_id, command)
                if duplicate:
                    equivalent = (
                        duplicate["customer_statement"] == command.customer_statement
                        and duplicate["reason_code"] == command.reason_code
                    )
                    if equivalent:
                        return _outcome(
                            "already_submitted",
                            correlation_id,
                            "An equivalent request is already under review.",
                            request_id=duplicate["request_id"],
                            request_state=duplicate["state"],
                        )
                    if command.action != "create":
                        return _outcome(
                            "invalid_state",
                            correlation_id,
                            "A change for this dispute is already under review.",
                        )

                if _rate_limited(
                    connection, customer_id, session_id, command.target_id, now
                ):
                    return _outcome(
                        "rate_limited",
                        correlation_id,
                        "Please contact support for help.",
                    )

                request_id = str(uuid4())
                connection.execute(
                    "INSERT INTO requests "
                    "(request_id, customer_id, session_id, verification_reference, "
                    "verification_method, verified_at, action, target_id, expected_version, "
                    "reason_code, customer_statement, consent_reference, idempotency_key, "
                    "command_digest, "
                    "correlation_id, state, created_at) VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        customer_id,
                        session_id,
                        context.verification_reference,
                        context.method,
                        context.verified_at.astimezone(UTC).isoformat(),
                        command.action,
                        command.target_id,
                        command.expected_version,
                        command.reason_code,
                        command.customer_statement,
                        consent.consent_reference,
                        consent.idempotency_key,
                        consent.command_digest,
                        correlation_id,
                        "accepted",
                        now.isoformat(),
                    ),
                )
                connection.execute(
                    "INSERT INTO outbox (event_id, request_id, state) VALUES (?, ?, ?)",
                    (str(uuid4()), request_id, "pending"),
                )
                record_audit_event(
                    connection,
                    event_name="disputes.request_accepted",
                    request_id=request_id,
                    decision_code="accepted",
                    created_at=now,
                )
            return _outcome(
                "accepted",
                correlation_id,
                "Your request was received for human review.",
                request_id=request_id,
                request_state="accepted",
            )
        except sqlite3.Error:
            return _outcome(
                "temporarily_unavailable",
                correlation_id,
                "Request acceptance is uncertain. Check its status before trying again.",
                retryable=True,
            )

    def get_request_status(
        self,
        context: VerificationContext | None,
        *,
        session_id: str,
        request_id: str | None = None,
        idempotency_key: str | None = None,
        now: datetime | None = None,
    ) -> CommandOutcome:
        now = now or datetime.now(UTC)
        try:
            customer_id = require_verified_session(
                context, session_id=session_id, action=DISPUTE_READ_SCOPE, now=now
            )
        except AccessDenied:
            return _outcome("unauthorized", "", "Verification is required.")
        if bool(request_id) == bool(idempotency_key):
            return _outcome("validation_failed", "", "Provide one request reference.")
        field = "request_id" if request_id else "idempotency_key"
        value = request_id or idempotency_key
        try:
            connection = self._store.connect()
            try:
                row = connection.execute(
                    f"SELECT request_id, state, result_code, correlation_id FROM requests "
                    f"WHERE customer_id = ? AND {field} = ?",
                    (customer_id, value),
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error:
            return _outcome(
                "temporarily_unavailable",
                "",
                "Request status is unavailable.",
                retryable=True,
            )
        if row is None:
            return _outcome("unauthorized", "", "Request unavailable.")
        if row["state"] == "rejected":
            return _outcome(
                row["result_code"] or "invalid_state",
                row["correlation_id"],
                "The request could not be applied. Please contact support.",
                request_id=row["request_id"],
                request_state="rejected",
            )
        return _outcome(
            "accepted",
            row["correlation_id"],
            "The request is recorded for human review.",
            request_id=row["request_id"],
            request_state=row["state"],
        )
