import re
import sqlite3
from datetime import datetime
from uuid import uuid4


def record_audit_event(
    connection: sqlite3.Connection,
    *,
    event_name: str,
    request_id: str,
    decision_code: str,
    created_at: datetime,
) -> None:
    if not re.fullmatch(r"[a-z]+(?:\.[a-z_]+)+", event_name):
        raise ValueError("Audit event names must be dotted and filterable")
    connection.execute(
        "INSERT INTO audit_events "
        "(event_id, event_name, request_id, decision_code, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), event_name, request_id, decision_code, created_at.isoformat()),
    )
