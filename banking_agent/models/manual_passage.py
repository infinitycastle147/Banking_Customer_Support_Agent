from dataclasses import dataclass
from datetime import date

from banking_agent.models.source_reference import SourceReference


@dataclass(frozen=True)
class ManualPassage:
    reference: SourceReference
    text: str
    keywords: tuple[str, ...]
    expires_on: date | None
    classification: str
