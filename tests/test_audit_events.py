from datetime import UTC, datetime

import pytest

from banking_agent.audit.events import record_audit_event


def test_audit_rejects_non_filterable_event_name():
    with pytest.raises(ValueError, match="dotted and filterable"):
        record_audit_event(
            None,
            event_name="[disputes] accepted",
            request_id="demo-request",
            decision_code="accepted",
            created_at=datetime.now(UTC),
        )
