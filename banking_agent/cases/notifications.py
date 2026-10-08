from urllib.parse import quote, urlparse

from banking_agent.models.staff_case_report import StaffCaseReport
from banking_agent.models.staff_notification import StaffNotification


def build_staff_notification(
    report: StaffCaseReport, *, secure_case_base_url: str
) -> StaffNotification:
    parsed = urlparse(secure_case_base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("A secure HTTPS case base URL is required")
    urgent = "unauthorized_activity_claim" in report.risk_triggers
    summary = {
        "create": "New dispute request awaiting human review.",
        "amend": "Dispute amendment awaiting human review.",
        "withdraw": "Dispute withdrawal request awaiting human review.",
    }[report.requested_action]
    if urgent:
        summary = "Unauthorized activity claim awaiting human review."
    return StaffNotification(
        priority="urgent" if urgent else "normal",
        reference_id=report.reference_id,
        redacted_summary=summary,
        secure_case_link=f"{secure_case_base_url.rstrip('/')}/cases/{quote(report.case_id, safe='')}",
    )
