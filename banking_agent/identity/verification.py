from datetime import UTC, datetime

from banking_agent.config.settings import VERIFICATION_MAX_AGE
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.verification_context import VerificationContext


def require_verified_session(
    context: VerificationContext | None,
    *,
    session_id: str,
    action: str,
    now: datetime | None = None,
) -> str:
    if context is None:
        raise AccessDenied("Verification is required.")

    now = now or datetime.now(UTC)
    timestamps = (context.verified_at, context.expires_at, now)
    if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
        raise AccessDenied("Verification is required.")
    if (
        not context.session_id
        or context.session_id != session_id
        or not context.customer_id
        or not context.method
        or action not in context.permitted_actions
        or context.verified_at > now
        or context.expires_at <= now
        or context.expires_at - context.verified_at > VERIFICATION_MAX_AGE
    ):
        raise AccessDenied("Verification is required.")
    return context.customer_id
