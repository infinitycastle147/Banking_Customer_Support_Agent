from dataclasses import dataclass

from banking_agent.models.manual_passage import ManualPassage


@dataclass(frozen=True)
class SearchResult:
    status: str
    passages: tuple[ManualPassage, ...]
