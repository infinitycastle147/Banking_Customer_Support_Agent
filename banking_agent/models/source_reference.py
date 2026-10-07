from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SourceReference:
    document_id: str
    version: str
    section: str
    effective_date: date
