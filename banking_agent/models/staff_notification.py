from dataclasses import dataclass


@dataclass(frozen=True)
class StaffNotification:
    priority: str
    reference_id: str
    redacted_summary: str
    secure_case_link: str
