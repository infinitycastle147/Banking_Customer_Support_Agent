import json
from datetime import date
from hashlib import sha256

import pytest

from banking_agent.knowledge.ingest import build_approved_index
from banking_agent.knowledge.retrieval import (
    load_approved_passages,
    search_approved_manual,
)


def manifest_entry(source_bytes, **overrides):
    entry = {
        "document_id": "synthetic-policy",
        "version": "1",
        "owner": "Demo documentation owner",
        "approved_by": "Demo reviewer",
        "approval_status": "approved",
        "classification": "public",
        "effective_date": "2026-01-01",
        "expires_on": "2027-01-01",
        "source_path": "manual.md",
        "source_sha256": sha256(source_bytes).hexdigest(),
        "sections": [{"section": "Demo help", "keywords": ["help hours"]}],
    }
    return entry | overrides


def write_manifest(path, entries):
    path.write_text(json.dumps({"documents": entries}), encoding="utf-8")


def test_ingests_approved_section_with_owner_version_and_hash(tmp_path):
    content = b"# Demo\n\n## Demo help\n\nFictional help is available on weekdays.\n"
    (tmp_path / "manual.md").write_bytes(content)
    manifest = tmp_path / "manifest.json"
    index = tmp_path / "index.json"
    write_manifest(manifest, [manifest_entry(content)])

    build_approved_index(manifest, index)
    result = search_approved_manual(
        "When are the help hours?",
        load_approved_passages(index),
        today=date(2026, 10, 8),
    )

    assert result.status == "found"
    assert result.passages[0].text == "Fictional help is available on weekdays."
    assert result.passages[0].reference.owner == "Demo documentation owner"
    assert result.passages[0].reference.version == "1"
    assert result.passages[0].reference.source_hash == sha256(content).hexdigest()


def test_changed_source_cannot_replace_an_existing_index(tmp_path):
    original = b"## Demo help\nOriginal guidance.\n"
    (tmp_path / "manual.md").write_bytes(original)
    manifest = tmp_path / "manifest.json"
    index = tmp_path / "index.json"
    write_manifest(manifest, [manifest_entry(original)])
    build_approved_index(manifest, index)
    old_index = index.read_bytes()
    (tmp_path / "manual.md").write_text("## Demo help\nChanged guidance.\n")

    with pytest.raises(ValueError, match="hash does not match"):
        build_approved_index(manifest, index)

    assert index.read_bytes() == old_index


def test_draft_and_staff_documents_are_excluded(tmp_path):
    content = b"## Demo help\nFictional public guidance.\n"
    (tmp_path / "manual.md").write_bytes(content)
    manifest = tmp_path / "manifest.json"
    index = tmp_path / "index.json"
    write_manifest(
        manifest,
        [
            manifest_entry(content),
            manifest_entry(content, document_id="draft", approval_status="draft"),
            manifest_entry(content, document_id="staff", classification="staff"),
        ],
    )

    build_approved_index(manifest, index)

    assert len(load_approved_passages(index)) == 1
    assert len(json.loads(index.read_text())["documents"]) == 1


@pytest.mark.parametrize(
    "source_path",
    ["../outside.md", "/tmp/outside.md", "manual.pdf"],
)
def test_ingestion_rejects_unapproved_source_paths(tmp_path, source_path):
    content = b"## Demo help\nFictional public guidance.\n"
    (tmp_path / "manual.md").write_bytes(content)
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest, [manifest_entry(content, source_path=source_path)])

    with pytest.raises(ValueError, match="Markdown file inside"):
        build_approved_index(manifest, tmp_path / "index.json")


def test_duplicate_version_is_rejected(tmp_path):
    content = b"## Demo help\nFictional public guidance.\n"
    (tmp_path / "manual.md").write_bytes(content)
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest, [manifest_entry(content), manifest_entry(content)])

    with pytest.raises(ValueError, match="Duplicate approved document version"):
        build_approved_index(manifest, tmp_path / "index.json")
