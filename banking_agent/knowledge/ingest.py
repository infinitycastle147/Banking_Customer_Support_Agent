import argparse
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from banking_agent.config.settings import (
    MAX_MANUAL_SECTION_CHARS,
    MAX_MANUAL_SOURCE_BYTES,
)


def _sections_from_markdown(content: str) -> dict[str, str]:
    sections = {}
    heading = None
    lines = []
    for line in content.splitlines():
        if line.startswith("## "):
            if heading is not None:
                if heading in sections:
                    raise ValueError("Duplicate manual section heading")
                sections[heading] = "\n".join(lines).strip()
            heading = line.removeprefix("## ").strip()
            lines = []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        if heading in sections:
            raise ValueError("Duplicate manual section heading")
        sections[heading] = "\n".join(lines).strip()
    return sections


def _approved_document(entry: dict, manifest_dir: Path) -> dict:
    if entry["approval_status"] != "approved" or entry["classification"] != "public":
        raise ValueError("Only approved public documents may be ingested")
    if not entry["owner"].strip() or not entry["approved_by"].strip():
        raise ValueError("Document owner and approver are required")
    effective_date = date.fromisoformat(entry["effective_date"])
    expires_on = (
        date.fromisoformat(entry["expires_on"]) if entry.get("expires_on") else None
    )
    if expires_on is not None and expires_on <= effective_date:
        raise ValueError("Document expiry must follow its effective date")

    source = (manifest_dir / entry["source_path"]).resolve()
    if not source.is_relative_to(manifest_dir) or source.suffix.lower() != ".md":
        raise ValueError(
            "Manual source must be a Markdown file inside the manifest directory"
        )
    if source.stat().st_size > MAX_MANUAL_SOURCE_BYTES:
        raise ValueError("Manual source exceeds the pilot size limit")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["source_sha256"]:
        raise ValueError("Manual source hash does not match the approved manifest")
    available = _sections_from_markdown(raw.decode("utf-8"))
    sections = []
    for section in entry["sections"]:
        heading = section["section"]
        text = available.get(heading, "")
        if not text or len(text) > MAX_MANUAL_SECTION_CHARS:
            raise ValueError(
                "Approved manual section is missing or exceeds the pilot limit"
            )
        keywords = section["keywords"]
        if not keywords or any(
            not isinstance(item, str) or not item.strip() for item in keywords
        ):
            raise ValueError("Each approved section needs search keywords")
        sections.append({"section": heading, "keywords": keywords, "text": text})
    return {
        "document_id": entry["document_id"],
        "version": entry["version"],
        "owner": entry["owner"],
        "approved_by": entry["approved_by"],
        "approval_status": "approved",
        "classification": "public",
        "effective_date": effective_date.isoformat(),
        "expires_on": expires_on.isoformat() if expires_on else None,
        "source_sha256": digest,
        "sections": sections,
    }


def build_approved_index(manifest_path: Path, output_path: Path) -> None:
    manifest_dir = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = [
        _approved_document(entry, manifest_dir)
        for entry in manifest["documents"]
        if entry["approval_status"] == "approved"
        and entry["classification"] == "public"
    ]
    versions = [(item["document_id"], item["version"]) for item in documents]
    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate approved document version")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump({"documents": documents}, output, indent=2)
            output.write("\n")
        os.replace(temporary_name, output_path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a bank-approved public manual index"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    build_approved_index(arguments.manifest, arguments.output)


if __name__ == "__main__":
    main()
