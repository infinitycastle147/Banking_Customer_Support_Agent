import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

from banking_agent.config.settings import MAX_MANUAL_SECTION_CHARS
from banking_agent.models.manual_passage import ManualPassage
from banking_agent.models.search_result import SearchResult
from banking_agent.models.source_reference import SourceReference


def load_approved_passages(path: Path | None) -> tuple[ManualPassage, ...]:
    if path is None:
        return ()

    index = json.loads(path.read_text(encoding="utf-8"))
    passages = []
    for document in index["documents"]:
        if document["approval_status"] != "approved":
            continue
        if document["classification"] != "public":
            continue
        if (
            not document["owner"].strip()
            or not document["approved_by"].strip()
            or not re.fullmatch(r"[0-9a-f]{64}", document["source_sha256"])
        ):
            raise ValueError("Approved manual metadata is incomplete")

        effective_date = date.fromisoformat(document["effective_date"])
        expires_on = (
            date.fromisoformat(document["expires_on"])
            if document.get("expires_on")
            else None
        )
        for section in document["sections"]:
            text = section["text"].strip()
            if not text or len(text) > MAX_MANUAL_SECTION_CHARS:
                raise ValueError("Approved manual section must contain bounded text")
            passages.append(
                ManualPassage(
                    reference=SourceReference(
                        document_id=document["document_id"],
                        version=document["version"],
                        section=section["section"],
                        effective_date=effective_date,
                        owner=document["owner"],
                        source_hash=document["source_sha256"],
                    ),
                    text=text,
                    keywords=tuple(section["keywords"]),
                    expires_on=expires_on,
                    classification="public",
                )
            )
    return tuple(passages)


def search_approved_manual(
    query: str, passages: tuple[ManualPassage, ...], *, today: date | None = None
) -> SearchResult:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return SearchResult(status="missing", passages=())

    today = today or datetime.now(UTC).date()
    words = set(re.findall(r"[a-z0-9]+", query.casefold()))
    matches = [
        passage
        for passage in passages
        if any(
            set(re.findall(r"[a-z0-9]+", keyword.casefold())) <= words
            for keyword in passage.keywords
            if keyword.strip()
        )
    ]
    current = [
        passage
        for passage in matches
        if passage.reference.effective_date <= today
        and (passage.expires_on is None or today < passage.expires_on)
    ]
    if not current:
        return SearchResult(status="missing", passages=())
    if len({passage.text for passage in current}) > 1:
        return SearchResult(status="conflict", passages=())
    selected = max(current, key=lambda passage: passage.reference.effective_date)
    return SearchResult(status="found", passages=(selected,))
